# Data Scientist Lead — Technical Assessment

Thanks for taking on this challenge. We have designed it to reflect the kind of problems you would solve day to day at Spot2.

## The challenge

You will build a **Lead Opportunity Score** for a commercial real estate marketplace. The score combines two questions:

1. **Lead Quality**: how likely is this lead to convert?
2. **Inventory Availability**: can our current inventory meet their needs?

Your final score gives us a single number for each lead: **Lead Opportunity Score = Lead Quality x Inventory Availability**.

When inventory is tight, your system should also suggest viable alternatives properties in the same sector and corridor.

## The data

You get 6 relational tables. Each is available in both CSV and Parquet format under `data/candidate/csv/` and `data/candidate/parquet/`.

| Table | Rows (approx) | What it contains |
|-------|---------------|------------------|
| `leads` | ~5,000 | Lead data: user type, target sector, budget, preferred location |
| `spots` | ~2,000–4,000 | Property catalog: sector, price per m2, area, location, modality |
| `spot_attributes` | ~2,000–4,000 | Property features: lighting, parking spaces, height, amenities |
| `inquiries` | ~15,000–25,000 | Lead-property contact history: channel, requested area, urgency |
| `market_context` | ~500 | Market context by state/municipality/corridor/sector/month |
| `availability_snapshot` | ~20,000–40,000 | Availability status per property at different points in time |

> Note: some labels used for evaluation (such as conversion outcomes) are intentionally withheld; your models should predict or infer the relevant target variables.

### Loading the data

Both formats are provided so you can choose what works best for your workflow.

**Pandas**

```python
import pandas as pd

# CSV
leads = pd.read_csv("data/candidate/csv/leads.csv")
spots = pd.read_csv("data/candidate/csv/spots.csv")

# Parquet (faster, smaller)
leads = pd.read_parquet("data/candidate/parquet/leads.parquet")
spots = pd.read_parquet("data/candidate/parquet/spots.parquet")
```

**Polars**

```python
import polars as pl

# CSV
leads = pl.read_csv("data/candidate/csv/leads.csv")
spots = pl.read_csv("data/candidate/csv/spots.csv")

# Parquet (faster, smaller)
leads = pl.read_parquet("data/candidate/parquet/leads.parquet")
spots = pl.read_parquet("data/candidate/parquet/spots.parquet")
```

### Data quality notes

Some columns have missing values and outliers. This is expected in real-world data. Decide how to handle them and justify your choices. No ground truth answer sheet exists for these decisions.

## What to deliver

1. **Notebook** (.ipynb or rendered HTML) with your full reproducible analysis.
2. **One-pager** (PDF) executive summary for Product and C-Level audiences.
3. **Slides** (PDF, 5–8 slides) with key findings for a 15-minute presentation.
4. **AI prompt** you used, included as a text block in the notebook.

## Time

We expect this to take about 6–8 hours. We do not expect production-ready infrastructure. We do expect a solid analysis, clearly communicated, with a path to scale.

## Tips

- The data is synthetic, designed so you can find realistic patterns. Do not look for perfect relationships.
- There are missing values and outliers deliberately placed. Your decisions on how to handle them are part of the evaluation.
- Some columns are leakage traps. Detecting them is part of the exercise.
- The product question matters as much as the model. Do not leave it for last.
- Use an LLM. Using AI is an explicit part of the evaluation.

Good luck, and have fun with it.
