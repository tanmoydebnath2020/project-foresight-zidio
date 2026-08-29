# foresight-northbay — Streamlit Planning Dashboard

Project FORESIGHT's D5 deliverable: an interactive dashboard covering everything the brief
asks for (Home, Sales Analytics, Forecast, Inventory, Risk Dashboard, Product Details,
Executive Summary) plus **2 extra pages** — a **What-If Simulator** and an **Alerts Center**
— and **16 different chart types** across the app (area, line, bar, grouped bar, box, treemap,
heatmap, scatter, bubble scatter, 3D scatter, waterfall, funnel, gauge/indicator, radar/polar,
sunburst, donut/pie).

This app ships with its own bundled, pre-processed data (`data/` folder) — it does **not**
need `online_retail_II.xlsx` or the notebooks to run. It's fully self-contained.

## Run it locally (2 minutes)
```bash
pip install -r requirements.txt
streamlit run app.py
```
Opens at `http://localhost:8501`.

## Deploy it for real — Streamlit Community Cloud (free, ~5 minutes)

This is the simplest option and the one the engagement brief recommends.

1. **Put this `app/` folder in a GitHub repo.**
   - Create a new repo (suggested name: `foresight-northbay`), public or private.
   - Upload everything inside this `app/` folder to the repo **root** (so `app.py`,
     `requirements.txt`, `data/`, and `.streamlit/` all sit at the top level — not nested
     inside another `app/` folder).
2. **Go to** [share.streamlit.io](https://share.streamlit.io) **and sign in with GitHub.**
3. Click **"New app"**, pick your repo/branch, and set:
   - Main file path: `app.py`
4. Click **Deploy**. Streamlit Cloud installs `requirements.txt` and starts the app — first
   deploy usually takes 2-3 minutes.
5. You'll get a live URL like `https://foresight-northbay.streamlit.app` — that's your D6-style
   public link, shareable with anyone (no login needed to view).

To push updates later: just push new commits to the GitHub repo — Streamlit Cloud
auto-redeploys.

## Alternative: Hugging Face Spaces (also free)
1. Create a new Space at [huggingface.co/new-space](https://huggingface.co/new-space), SDK =
   **Streamlit**.
2. Upload the same files (`app.py`, `requirements.txt`, `data/`, `.streamlit/`) to the Space's
   repo root.
3. The Space builds and serves the app automatically at
   `https://huggingface.co/spaces/<your-username>/<space-name>`.

## Alternative: Render.com
1. New **Web Service** → connect the GitHub repo.
2. Build command: `pip install -r requirements.txt`
3. Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

## What's inside
```
app/
  app.py                 # the whole application (9 pages)
  requirements.txt
  .streamlit/config.toml # brand theme (purple/indigo)
  data/                  # pre-computed, bundled — no external dependency at runtime
    sales_daily.csv
    sku_master.csv
    calendar.csv
    weekly.csv
    inventory_snapshots.csv   (last 120 days per SKU — trimmed for repo size)
    production_forecast.csv
    risk_table.csv
    model_metrics.json
```

## Data refresh
This dashboard reads static CSVs — it does not re-run the forecast live. To refresh it with
new data, re-run the analysis notebook (or `src/run_pipeline.py` + the modeling/risk cells) and
overwrite the CSVs in `app/data/` with the new output, keeping the same filenames and columns.

## Known limitations (same as the notebook — carry these into any client conversation)
- `inventory_snapshots` and SKU `unit_cost` are **simulated** (no real feed was provided).
- Forecast WAPE is in the 0.6-0.8 range — directionally useful for prioritisation, not precise
  enough for exact order quantities.
- Category labels are keyword-derived from product descriptions, not a real merchandising
  taxonomy.
