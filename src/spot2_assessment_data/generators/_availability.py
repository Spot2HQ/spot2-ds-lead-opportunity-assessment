"""generate_availability_snapshot — availability snapshots for spots."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
import polars as pl

from spot2_assessment_data.config import AssessmentConfig
from spot2_assessment_data.rng import SeedRng


def generate_availability_snapshot(
    spots_df: pl.DataFrame,
    inquiries_df: pl.DataFrame,
    rng: SeedRng,
    config: AssessmentConfig,
) -> pl.DataFrame:
    """Generate availability_snapshot table (~30000 rows).

    Snapshots are generated around inquiry dates, with ~60-70% available,
    biased toward unavailable for inactive spots.
    """
    n_target = config.row_counts.availability_snapshot
    spot_ids = spots_df["spot_id"].to_list()
    n_spots = len(spot_ids)

    # Build spot lookup: created_at date + is_active
    spot_created: dict[int, date] = {}
    spot_active: dict[int, bool] = {}
    for row in spots_df.iter_rows(named=True):
        sid = row["spot_id"]
        d = row["created_at"]
        dt = d.date() if isinstance(d, datetime) else d
        spot_created[sid] = dt
        spot_active[sid] = row["is_active"]

    # Build spot activity density from inquiries
    spot_inquiry_counts: dict[int, int] = {}
    for sid in inquiries_df["spot_id"].to_list():
        spot_inquiry_counts[sid] = spot_inquiry_counts.get(sid, 0) + 1

    inquiry_dates = inquiries_df["inquiry_at"].to_list()
    min_date = min(d.date() for d in inquiry_dates if d is not None)
    max_date = max(d.date() for d in inquiry_dates if d is not None)
    total_days = (max_date - min_date).days

    max_date_allowed = config.temporal_range.end

    rows: list[dict] = []
    snap_id = 1
    seen: set[tuple[int, str]] = set()

    # Oversample to account for dedup skipping; break when we hit target
    for _ in range(n_target * 2):
        if len(rows) >= n_target:
            break

        sid = spot_ids[rng.rng.integers(0, n_spots)]

        # Snapshot date near a random inquiry date
        if inquiry_dates:
            ref_date = inquiry_dates[rng.rng.integers(0, len(inquiry_dates))]
            offset = int(rng.rng.integers(-7, 8))
            snap_date = (ref_date + timedelta(days=offset)).date()
        else:
            day_offset = int(rng.rng.integers(0, max(total_days, 1)))
            snap_date = min_date + timedelta(days=day_offset)

        # Fix 1: snapshot_date must not be before spot was created
        created = spot_created.get(sid)
        if created and snap_date < created:
            snap_date = created

        # Fix 4: cap at config temporal range end
        if snap_date > max_date_allowed:
            snap_date = max_date_allowed

        # Fix 3: dedup (spot_id, snapshot_date)
        snap_key = (sid, snap_date.strftime("%Y-%m-%d"))
        if snap_key in seen:
            continue
        seen.add(snap_key)

        # Fix 2: bias inactive spots toward unavailable; raise active base
        # to compensate (target overall is_available rate: 0.58-0.72)
        is_active = spot_active.get(sid, True)
        activity = spot_inquiry_counts.get(sid, 0)
        if not is_active:
            avail_prob = 0.2
        else:
            avail_prob = 0.72 - 0.01 * min(activity, 10)
        is_available = rng.rng.random() < avail_prob

        if is_available:
            days_until = 0
        else:
            days_until = max(1, int(rng.rng.exponential(60)))

        # competing_inquiries_30d: from inquiry density
        comp = min(20, max(0, activity // 2 + rng.rng.poisson(2)))

        rows.append({
            "snapshot_id": snap_id,
            "spot_id": sid,
            "snapshot_date": snap_date.strftime("%Y-%m-%d"),
            "is_available": is_available,
            "days_until_available": days_until,
            "competing_inquiries_30d": comp,
        })
        snap_id += 1

    df = pl.DataFrame(rows)
    df = df.with_columns([
        pl.col("snapshot_date").str.strptime(pl.Date, "%Y-%m-%d"),
    ])

    return df
