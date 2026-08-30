# 🚀 foresight-northbay — Enterprise Planning & Sales Analytics Dashboard

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://foresight-northbay.streamlit.app)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

**foresight-northbay** is an interactive enterprise planning and revenue intelligence platform built for **Project FORESIGHT** (Deliverable D5). It unifies multi-page historical sales analytics, ML-driven demand forecasting, inventory health tracking, risk monitoring, scenario simulation, and automated alerting into a single Streamlit application.

The application ships with its own bundled, pre-processed datasets (`data/`) and is completely self-contained—requiring no external database, raw Excel files, or runtime notebooks to run.

---

## 📌 Page Architecture

The platform spans **9 dedicated pages**, combining core business requirements with advanced analytical features:

| Page | Core Purpose | Primary Outputs & Metrics |
| :--- | :--- | :--- |
| **🏠 Home** | High-level system overview & quick stats | Top-level KPIs, system health status, navigation shortcuts |
| **📊 Sales Analytics** | Revenue performance & category distribution | YoY/MoM revenue velocity, regional share, product mix |
| **🔮 Forecast** | Predictive demand trajectory | ML baseline demand, seasonality curves, prediction intervals |
| **📦 Inventory** | Stock health & supply chain tracking | Days of supply (DOS), stockout risk scores, reorder flags |
| **⚠️ Risk Dashboard** | Operational threat matrix | Revenue volatility metrics, outlier detection, anomaly scores |
| **🔎 Product Details** | Single-SKU granular deep dive | SKU economics, historical unit cost curves, demand stability |
| **📋 Executive Summary** | Board-ready briefing & synthesis | Synthesized executive insights, exportable summary metrics |
| **🎛️ What-If Simulator** | Interactive strategy & scenario modeling | Dynamic price elasticity, supply shock & margin impact tests |
| **🔔 Alerts Center** | Real-time threshold monitoring | Automated log for stock breaches, margin drops, revenue spikes |

---

## 🎨 Visual Analytics Engine

The app incorporates **16 distinct chart types** powered by Plotly to deliver multi-dimensional business views:

* **Trend & Velocity:** Area Chart, Line Chart, Grouped Bar Chart, Waterfall Chart
* **Distribution & Spread:** Box Plot, Heatmap, Scatter Plot, 3D Scatter Plot
* **Hierarchical & Share:** Treemap, Sunburst Chart, Donut / Pie Chart
* **Flow & Performance:** Funnel Chart, Bubble Scatter Plot, Gauge / Indicator, Radar / Polar Chart

---

## 📂 Repository Structure

```text
app/
├── app.py                      # Main Streamlit engine & multi-page navigation router
├── requirements.txt            # Python dependencies (Streamlit, Plotly, Pandas, etc.)
├── .streamlit/
│   └── config.toml             # Custom enterprise branding & visual theme (purple/indigo)
└── data/                       # Pre-computed, bundled datasets (no live DB connection needed)
    ├── sales_daily.csv         # Daily aggregated transaction history
    ├── sku_master.csv          # Catalog metadata, category mappings, and unit costs
    ├── calendar.csv            # Date dimension lookup, seasonality, and holiday flags
    ├── weekly.csv              # Weekly rollup statistics
    ├── inventory_snapshots.csv # 120-day historical stock level snapshots
    ├── production_forecast.csv # Model inference outputs and projected demand values
    ├── risk_table.csv          # Pre-computed risk indices and anomaly flags
    └── model_metrics.json      # Forecast evaluation metrics (WAPE, MAPE, RMSE)
```
## Installation

# 1. Clone the repository
git clone [https://github.com/your-username/foresight-northbay.git](https://github.com/your-username/foresight-northbay.git)
cd foresight-northbay

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the Streamlit application
streamlit run app.py

## ⚠️ Known Assumptions & Limitations
Simulated Metrics: inventory_snapshots and SKU unit_cost are statistically simulated due to missing operational ERP feeds.

Forecast Range: Model WAPE falls within the 0.60–0.80 range—offering strong directional guidance for inventory prioritization, but not intended for automated purchasing execution.

Taxonomy: Product categories are derived via keyword parsing from transaction descriptions rather than an official enterprise merchandising taxonomy.

# 📜 License
Distributed under the MIT License.
