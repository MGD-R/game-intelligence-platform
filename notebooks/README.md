# Analysis Notebook Guide

Suggested first notebooks after the data stage is built:

- `01_data_quality_and_anomalies.ipynb`
- `02_entity_resolution_feature_base.ipynb`
- `03_source_coverage.ipynb`
- `03_ml_research_defense_report.ipynb`

Recommended workflow:

1. Run `make ml-ready-data`.
2. Open the `data/processed` parquet snapshots.
3. Run `make er-merge-strategy-comparison`.
4. Run `make ml-research-defense`.
5. Review `data/artifacts/reports` and `data/artifacts/manifests`.

Keep notebook outputs lightweight and do not commit executed outputs or large generated artifacts.
