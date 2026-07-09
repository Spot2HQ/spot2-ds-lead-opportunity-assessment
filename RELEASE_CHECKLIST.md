# Release Checklist — Spot2 DS Lead Opportunity Assessment

## Yearly assessment refresh

### 1. Update docs
- [ ] Review `assessment.md` — are all 8 deliverables still relevant?
- [ ] Review `feature_dictionary.md` — do field definitions, units, nullability, and join keys match the candidate data?
- [ ] Update `synthetic-data-guide.md` if generation rules changed
- [ ] Update `reviewer-rubric.md` if evaluation criteria changed
- [ ] Update year in config `config/default.yaml` temporal_range

### 2. Discover schemas (optional)
- [ ] If ClickHouse has new tables/columns: `uv run python scripts/discover_clickhouse_shapes.py --output .omo/evidence/clickhouse-shapes-summary-<year>.json --schema-only`
- [ ] Or skip and use existing `config/geo_reference_seed.yaml`

### 3. Generate data
```bash
uv run python scripts/generate_assessment_data.py --seed 42 --config config/default.yaml --output data
```
- [ ] Verify row counts in `data/manifest.json`
- [ ] `uv run pytest tests -q` — all generator tests pass
- [ ] `uv run python scripts/validate_generated_data.py --data-dir data --evidence .omo/evidence/generated-data-validation-<year>.json`

### 4. Build candidate bundle
```bash
uv run python scripts/package_candidate_bundle.py --data-dir data --output dist/spot2-ds-lead-opportunity-assessment-<year>.zip
```
- [ ] Verify bundle contents: `python3 -c "import zipfile; [print(n) for n in sorted(zipfile.ZipFile('dist/spot2-ds-lead-opportunity-assessment-<year>.zip').namelist())]"`
- [ ] Confirm `feature_dictionary.md` is expected in the ZIP and no `synthetic-data-guide.md` or `reviewer-rubric.md` is in the ZIP; also confirm NO outcomes*, evaluation/, internal/, scripts/, src/, tests/, config/, .omo/, .git/ in bundle

### 5. Internal review
- [ ] Review hidden `data/evaluation/parquet/outcomes.parquet` base rates
- [ ] Spot-check candidate data files manually
- [ ] Run full validation: `uv run pytest tests -q`

### 6. Share
- [ ] Send `dist/spot2-ds-lead-opportunity-assessment-<year>.zip` to candidate
- [ ] Archive evidence files to `.omo/evidence/<year>/`

### 7. Archive (optional, only if using git)
- [ ] Tag: `git tag assessment-<year>`
- [ ] Commit docs changes if any
- [ ] Push tag and commits
