"""generate_spots — synthetic spots table generator."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

import numpy as np
import polars as pl

from spot2_assessment_data.config import AssessmentConfig
from spot2_assessment_data.constants import Sector
from spot2_assessment_data.distributions import area_sqm as dist_area_sqm
from spot2_assessment_data.distributions import price_per_sqm as dist_price_sqm
from spot2_assessment_data.distributions import days_on_market as dist_dom
from spot2_assessment_data.geo_catalog import GeoCatalog, LocationAnchor
from spot2_assessment_data.rng import SeedRng

SECTOR_NAMES: Final[list[str]] = ["Industrial", "Office", "Retail", "Land"]
_SECTOR_WEIGHTS: Final[list[float]] = [0.30, 0.30, 0.25, 0.15]
_TYPE_NAMES: Final[list[str]] = ["Single", "Subspace"]
_TYPE_WEIGHTS: Final[list[float]] = [0.70, 0.30]
_MODALITIES: Final[list[str]] = ["rent", "sale", "both"]
_MODALITY_WEIGHTS: Final[list[float]] = [0.40, 0.25, 0.35]

# Maps sector display name -> Sector enum for dist module lookups.
_SECTOR_MAP: Final[dict[str, Sector]] = {
    "Industrial": Sector.INDUSTRIAL,
    "Office": Sector.OFFICE,
    "Retail": Sector.RETAIL,
    "Land": Sector.LAND,
}

# Title templates per type.
_TITLE_TEMPLATES: Final[dict[str, list[str]]] = {
    "Single": [
        "{type_name} {sector} en {corridor}, {municipality}",
        "{sector} {type_name} - {corridor}, {municipality}",
        "{type_name} de {area} m² en {corridor}",
    ],
    "Subspace": [
        "{type_name} en {sector} - {corridor}, {municipality}",
        "{sector} compartido en {corridor}, {municipality}",
        "{type_name} {area} m², {corridor}",
    ],
}

_DESC_PHRASES: Final[list[str]] = [
    "Excelente ubicación con acceso a vías principales.",
    "Espacio listo para ocupar con acabados de primera.",
    "Ideal para oficinas corporativas o centro de distribución.",
    "Cuenta con todos los servicios y estacionamiento.",
    "Zona de alta plusvalía y demanda comercial.",
    "Fácil acceso a transporte público y avenidas principales.",
    "Perfecto para negocio en crecimiento.",
    "Amplio espacio con buena iluminación natural.",
    "Recién remodelado con acabados modernos.",
    "Ubicación estratégica cerca de centros comerciales.",
    "Espacio versátil adaptable a diferentes giros.",
    "Seguridad 24/7 y control de acceso.",
]


def _pick_weighted(rng: SeedRng, items: list[str], weights: list[float], n: int) -> list[str]:
    probs = np.asarray(weights, dtype=np.float64) / sum(weights)
    idx = rng.rng.choice(len(items), size=n, p=probs)
    return [items[i] for i in idx]


def _generate_title(
    type_name: str, sector: str, corridor: str, municipality: str,
    area: float, rng: SeedRng,
) -> str:
    templates = _TITLE_TEMPLATES.get(type_name, _TITLE_TEMPLATES["Single"])
    tmpl = templates[rng.rng.integers(0, len(templates))]
    return tmpl.format(
        type_name=type_name, sector=sector,
        corridor=corridor, municipality=municipality,
        area=int(area),
    )


def _generate_description(rng: SeedRng) -> str:
    n = rng.rng.integers(1, 4)
    idx = rng.rng.choice(len(_DESC_PHRASES), size=n, replace=False)
    return " ".join(_DESC_PHRASES[i] for i in idx)


def generate_spots(
    rng: SeedRng,
    config: AssessmentConfig,
    geo_catalog: GeoCatalog,
) -> pl.DataFrame:
    """Generate the synthetic spots table (~3000 rows)."""
    n = config.row_counts.spots
    max_jitter = config.geo_jitter.max_km

    spot_ids = list(range(1, n + 1))

    # --- Broker IDs: ~300 unique, 70% 1-5 spots, 30% 6+ ---
    n_brokers = 300
    broker_pool = list(range(1, n_brokers + 1))
    heavy_brokers = broker_pool[:int(n_brokers * 0.3)]
    light_brokers = broker_pool[int(n_brokers * 0.3):]
    broker_ids: list[int] = []
    for _ in range(n):
        if rng.rng.random() < 0.3:
            broker_ids.append(heavy_brokers[rng.rng.integers(0, len(heavy_brokers))])
        else:
            broker_ids.append(light_brokers[rng.rng.integers(0, len(light_brokers))])

    # --- Sector and type ---
    sector_names = _pick_weighted(rng, SECTOR_NAMES, _SECTOR_WEIGHTS, n)
    type_names = _pick_weighted(rng, _TYPE_NAMES, _TYPE_WEIGHTS, n)

    # --- Geo: each spot gets an anchor with jitter ---
    anchors: list[LocationAnchor] = []
    lats: list[float] = []
    lons: list[float] = []
    for _ in range(n):
        anchor = geo_catalog.get_valid_anchor()
        anchors.append(anchor)
        lat, lon = geo_catalog.generate_spot_location(anchor, max_jitter)
        lats.append(round(lat, 6))
        lons.append(round(lon, 6))

    states = [a.state for a in anchors]
    municipalities = [a.municipality for a in anchors]
    settlements = [a.settlement for a in anchors]
    corridors = [a.corridor for a in anchors]
    regions = [a.region for a in anchors]

    # --- Area per sector using distributions module ---
    area_vals: list[float] = []
    for s in sector_names:
        sec = _SECTOR_MAP[s]
        area_vals.append(round(dist_area_sqm(sec, rng), 1))

    # --- Prices ---
    rent_prices: list[float] = []
    sale_prices: list[float] = []
    for s in sector_names:
        sec = _SECTOR_MAP[s]
        rp = dist_price_sqm(sec, rng)
        rent_prices.append(round(rp, 2))
        sp = rp * 180 * rng.rng.uniform(0.8, 1.2)
        sale_prices.append(round(sp, 2))

    area_arr = np.array(area_vals)
    rent_arr = np.array(rent_prices)
    sale_arr = np.array(sale_prices)
    total_rent = (area_arr * rent_arr).round(2)
    total_sale = (area_arr * sale_arr).round(2)
    maintenance = (total_rent * rng.rng.uniform(0.05, 0.15, size=n)).round(2)

    # --- Modality ---
    modality = _pick_weighted(rng, _MODALITIES, _MODALITY_WEIGHTS, n)

    # --- Days on market ---
    dom_vals: list[int] = []
    for s in sector_names:
        sec = _SECTOR_MAP[s]
        d = min(dist_dom(rng, sec), 730)
        dom_vals.append(d)

    # --- Inquiries and views correlated with DOM and sector ---
    dom_arr = np.array(dom_vals, dtype=np.float64)
    sector_hotness = {"Industrial": 1.2, "Office": 1.5, "Retail": 1.0, "Land": 0.6}
    hot = np.array([sector_hotness[s] for s in sector_names])
    total_inquiries = np.maximum(0, (dom_arr * hot * rng.rng.uniform(0.01, 0.05, size=n) + rng.rng.poisson(3, size=n)).astype(int))
    total_views = (total_inquiries * rng.rng.uniform(10, 30, size=n)).astype(int)

    # --- is_active: 88% ---
    is_active = (rng.rng.random(n) < 0.88).tolist()

    # --- created_at: pre-existing 2024-2025 + project timeline ---
    t_start_earliest = datetime(2024, 1, 1)
    t_start_main = config.start_datetime  # 2025-01-01
    t_end = config.end_datetime           # 2026-06-30
    pre_existing_days = (t_start_main - t_start_earliest).days
    main_days = (t_end - t_start_main).days
    created_at: list[str] = []
    for _ in range(n):
        if rng.rng.random() < 0.25:
            # Pre-existing inventory: 2024-01-01 .. 2024-12-31
            offset = int(rng.rng.integers(0, pre_existing_days))
            created = t_start_earliest + timedelta(days=offset)
        else:
            # Project timeline: 2025-01-01 .. 2026-06-30
            offset = int(rng.rng.integers(0, main_days + 1))
            created = t_start_main + timedelta(days=offset)
        created_at.append(created.strftime("%Y-%m-%d %H:%M:%S"))

    # --- Titles and descriptions ---
    titles = [
        _generate_title(t, s, c, m, a, rng)
        for t, s, c, m, a in zip(type_names, sector_names, corridors, municipalities, area_vals)
    ]
    descriptions = [_generate_description(rng) for _ in range(n)]

    df = pl.DataFrame({
        "spot_id": spot_ids,
        "broker_id": broker_ids,
        "sector_name": sector_names,
        "type_name": type_names,
        "state": states,
        "municipality": municipalities,
        "settlement": settlements,
        "corridor": corridors,
        "region": regions,
        "lat": lats,
        "lon": lons,
        "title": titles,
        "description": descriptions,
        "area_sqm": area_vals,
        "price_sqm_mxn_rent": rent_prices,
        "price_sqm_mxn_sale": sale_prices,
        "price_total_mxn_rent": total_rent.tolist(),
        "price_total_mxn_sale": total_sale.tolist(),
        "maintenance_cost_mxn": maintenance.tolist(),
        "modality": modality,
        "days_on_market": dom_vals,
        "total_inquiries": total_inquiries.tolist(),
        "total_views": total_views.tolist(),
        "is_active": is_active,
        "created_at": created_at,
    })

    # Convert datetime column
    df = df.with_columns([
        pl.col("created_at").str.strptime(pl.Datetime("us"), "%Y-%m-%d %H:%M:%S"),
    ])

    return df
