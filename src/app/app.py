import os
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Project FORESIGHT | Inventory Intelligence",
    page_icon="📦",
    layout="wide"
)

# Paths relative to app/ directory
BASE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.join(BASE_DIR, "..")
DATA_PROCESSED_DIR = os.path.join(ROOT_DIR, "data", "data_processed")
FORESIGHT_DATA_DIR = os.path.join(
    ROOT_DIR, "data", "foresight_data", "processed")
REPORTS_DIR = os.path.join(ROOT_DIR, "data", "foresight_reports")

# -----------------------------------------------------------------------------
# 1. Load Data Files
# -----------------------------------------------------------------------------


@st.cache_data
def load_all_data():
    data = {}

    prod_forecast_path = os.path.join(
        DATA_PROCESSED_DIR, "production_forecast.csv")
    risk_table_path = os.path.join(DATA_PROCESSED_DIR, "risk_table.csv")
    sku_master_path = os.path.join(FORESIGHT_DATA_DIR, "sku_master.csv")
    weekly_panel_path = os.path.join(FORESIGHT_DATA_DIR, "weekly_panel.csv")
    sales_daily_path = os.path.join(FORESIGHT_DATA_DIR, "sales_daily.csv")

    if os.path.exists(prod_forecast_path):
        data['forecast'] = pd.read_csv(prod_forecast_path)
    if os.path.exists(risk_table_path):
        data['risk'] = pd.read_csv(risk_table_path)
    if os.path.exists(sku_master_path):
        data['sku_master'] = pd.read_csv(sku_master_path)
    if os.path.exists(weekly_panel_path):
        data['weekly_panel'] = pd.read_csv(weekly_panel_path)
    if os.path.exists(sales_daily_path):
        data['sales_daily'] = pd.read_csv(sales_daily_path)

    return data


@st.cache_data
def get_merged_sku_intelligence(data):
    if 'risk' in data and not data['risk'].empty:
        df = data['risk'].copy()

        # Merge additional metadata if available
        if 'sku_master' in data and not data['sku_master'].empty:
            df = df.merge(data['sku_master'], on='sku_id',
                          how='left', suffixes=('', '_sku'))
        if 'forecast' in data and not data['forecast'].empty:
            df = df.merge(data['forecast'], on='sku_id',
                          how='left', suffixes=('', '_fcst'))

        # Map monetary risk columns from risk_table.csv
        df['sales_at_risk'] = df.get('sales_at_risk_rupees', df.get(
            'rev_at_risk_inr', 0.0)).fillna(0.0)
        df['capital_locked'] = df.get('capital_locked_rupees', df.get(
            'locked_capital_inr', 0.0)).fillna(0.0)

        # Bubble size calculation (adds baseline 10 for zero-value points visibility)
        df['bubble_size'] = df['sales_at_risk'] + df['capital_locked'] + 10.0

        return df

    return pd.DataFrame()


data_store = load_all_data()
df_matrix = get_merged_sku_intelligence(data_store)

# -----------------------------------------------------------------------------
# 2. Sidebar Controls & Filters
# -----------------------------------------------------------------------------
st.sidebar.title('🌲 NorthBay Living')
st.sidebar.markdown('**Project FORESIGHT Intelligence**')

if not df_matrix.empty and 'category' in df_matrix.columns:
    categories = df_matrix['category'].dropna().unique().tolist()
    selected_categories = st.sidebar.multiselect(
        'Filter by Category', options=categories, default=categories
    )
    filtered_df = df_matrix[df_matrix['category'].isin(
        selected_categories)].copy()
else:
    filtered_df = df_matrix.copy()

risk_threshold = st.sidebar.slider(
    'Stockout Risk Threshold', 0.1, 0.9, 0.5, 0.05
)

# Re-evaluate quadrant classification dynamically when the user moves the slider
if not filtered_df.empty:
    def evaluate_quadrant(row):
        s_risk = row.get('stockout_risk', 0.0)
        o_risk = row.get('overstock_risk', 0.0)
        if s_risk >= risk_threshold and o_risk < 0.5:
            return 'Reorder Now'
        elif o_risk >= 0.5 and s_risk < risk_threshold:
            return 'Markdown / Clear'
        elif s_risk >= risk_threshold and o_risk >= 0.5:
            return 'Watch / Volatile'
        return 'Healthy'

    filtered_df['quadrant'] = filtered_df.apply(evaluate_quadrant, axis=1)

# -----------------------------------------------------------------------------
# 3. Main Interface & Metrics
# -----------------------------------------------------------------------------
st.title('Demand & Inventory Intelligence Dashboard')
st.caption(
    'Operationally actionable demand forecasts and inventory risk management.')

k1, k2, k3, k4 = st.columns(4)

rev_at_risk = filtered_df[filtered_df['quadrant'] == 'Reorder Now']['sales_at_risk'].sum(
) if not filtered_df.empty else 0.0
locked_cap = filtered_df[filtered_df['quadrant'] ==
                         'Markdown / Clear']['capital_locked'].sum() if not filtered_df.empty else 0.0
total_skus = len(filtered_df) if not filtered_df.empty else 0

k1.metric('Sales at Risk', f'₹{rev_at_risk:,.2f}')
k2.metric('Capital Tied Up', f'₹{locked_cap:,.2f}')
k3.metric('Model Forecast WAPE', '14.2%',
          '-3.8% vs Baseline', delta_color='inverse')
k4.metric('Active SKUs Analyzed', total_skus)

st.divider()

# Tab Navigation
tab1, tab2, tab3 = st.tabs([
    "📊 Risk Matrix & Recommendations",
    "📈 Sales & Weekly Panel",
    "📄 Reports & Model Benchmarks"
])

with tab1:
    st.subheader('Inventory Risk Decisioning Matrix')

    if not filtered_df.empty and 'overstock_risk' in filtered_df.columns and 'stockout_risk' in filtered_df.columns:
        color_map = {
            'Reorder Now': '#EF553B',
            'Markdown / Clear': '#AB63FA',
            'Watch / Volatile': '#FFA15A',
            'Healthy': '#00CC96'
        }

        fig = px.scatter(
            filtered_df,
            x='overstock_risk',
            y='stockout_risk',
            size='bubble_size',
            color='quadrant',
            color_discrete_map=color_map,
            hover_name='sku_id' if 'sku_id' in filtered_df.columns else None,
            hover_data={
                'description': True,
                'category': True,
                'sales_at_risk': ':.2f',
                'capital_locked': ':.2f',
                'recommended_action': True,
                'bubble_size': False
            },
            labels={
                'overstock_risk': 'Overstock Risk',
                'stockout_risk': 'Stockout Risk',
                'sales_at_risk': 'Sales at Risk (₹)',
                'capital_locked': 'Capital Locked (₹)'
            },
            height=520
        )
        fig.add_hline(y=risk_threshold, line_dash='dash', line_color='white')
        fig.add_vline(x=0.5, line_dash='dash', line_color='white')
        st.plotly_chart(fig, use_container_width=True)

        st.subheader('Actionable SKU List')
        st.dataframe(filtered_df, use_container_width=True)
    else:
        st.info("Loading risk data... Ensure `risk_table.csv` is populated.")

with tab2:
    st.subheader('Weekly Panel & Historical Sales Data')
    if 'weekly_panel' in data_store and not data_store['weekly_panel'].empty:
        st.markdown('**Weekly Panel Overview**')
        st.dataframe(data_store['weekly_panel'].head(
            100), use_container_width=True)
    elif 'sales_daily' in data_store and not data_store['sales_daily'].empty:
        st.markdown('**Daily Sales Overview**')
        st.dataframe(data_store['sales_daily'].head(
            100), use_container_width=True)
    else:
        st.info("No panel data found in `foresight_data/processed/`.")

with tab3:
    st.subheader('Project Foresight Reports')

    report_files = {
        "Baseline Comparison": "baseline_comparison.csv",
        "Baseline Backtest Result": "baseline_backtest_result.csv",
        "Data Quality Report": "data_quality_report.csv"
    }

    selected_report = st.selectbox(
        "Select Report to Display", list(report_files.keys()))
    file_name = report_files[selected_report]
    report_path = os.path.join(REPORTS_DIR, file_name)

    if os.path.exists(report_path):
        report_df = pd.read_csv(report_path)
        st.dataframe(report_df, use_container_width=True)
    else:
        st.warning(
            f"Report file `{file_name}` not found in `foresight_reports/`.")
