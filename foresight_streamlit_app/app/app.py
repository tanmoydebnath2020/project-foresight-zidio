"""
foresight-northbay — Project FORESIGHT: Demand & Inventory Intelligence
Streamlit planning dashboard for NorthBay Living (Zidio Development engagement, D5 deliverable)

Run locally:   streamlit run app.py
Deploy: see README_DEPLOY.md (suggested repo/app name: foresight-northbay)
"""
import os
import json
import inspect
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import calendar as calmod

# --------------------------------------------------------------------------------------
# Page config + custom styling (make it feel like a real product, not a default Streamlit app)
# --------------------------------------------------------------------------------------
st.set_page_config(
    page_title="FORESIGHT — NorthBay Living",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded",
)

BRAND_PRIMARY = "#3F3D8A"
BRAND_ACCENT = "#6C63FF"
BRAND_LIGHT = "#F5F4FC"
COLOR_MAP = {
    "Reorder Now": "#D9534F",
    "Markdown / Clear": "#5B5FC7",
    "Watch / Volatile": "#E0A800",
    "Healthy": "#4CAF50",
}

st.markdown(f"""
<style>
    html, body, [class*="css"] {{ font-family: 'Inter', 'Segoe UI', sans-serif; }}
    .main {{ background-color: #FFFFFF; }}
    #MainMenu, footer {{visibility: hidden;}}

    section[data-testid="stSidebar"] {{ background-color: {BRAND_PRIMARY}; }}
    section[data-testid="stSidebar"] * {{ color: #FFFFFF !important; }}
    section[data-testid="stSidebar"] .stRadio > label {{ font-weight: 600; }}

    .kpi-card {{
        background: linear-gradient(135deg, {BRAND_LIGHT} 0%, #FFFFFF 100%);
        border: 1px solid #E4E2F5; border-radius: 14px; padding: 18px 20px;
        box-shadow: 0 2px 10px rgba(63,61,138,0.06); height: 100%;
    }}
    .kpi-label {{ font-size: 0.80rem; color: #6B6890; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }}
    .kpi-value {{ font-size: 1.65rem; color: {BRAND_PRIMARY}; font-weight: 800; margin-top: 4px; }}
    .kpi-sub {{ font-size: 0.78rem; color: #8A87AC; margin-top: 2px; }}

    .section-title {{
        font-size: 1.35rem; font-weight: 800; color: {BRAND_PRIMARY};
        border-left: 5px solid {BRAND_ACCENT}; padding-left: 12px; margin: 6px 0 14px 0;
    }}

    .alert-card {{
        border-radius: 12px; padding: 14px 16px; margin-bottom: 10px;
        border-left: 6px solid #ccc; background: #FAFAFC;
    }}
    .badge {{
        display: inline-block; padding: 2px 10px; border-radius: 999px;
        font-size: 0.72rem; font-weight: 700; color: white; margin-right: 8px;
    }}

    div[data-testid="stMetricValue"] {{ color: {BRAND_PRIMARY}; }}
    .stTabs [data-baseweb="tab"] {{ font-weight: 600; }}
</style>
""", unsafe_allow_html=True)

PLOTLY_TEMPLATE = "plotly_white"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


# --------------------------------------------------------------------------------------
# Data loading (cached)
# --------------------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading FORESIGHT data...")
def load_data():
    sales_daily = pd.read_csv(f"{DATA_DIR}/sales_daily.csv", parse_dates=["date"])
    sku_master = pd.read_csv(f"{DATA_DIR}/sku_master.csv", parse_dates=["launch_date"])
    calendar_df = pd.read_csv(f"{DATA_DIR}/calendar.csv", parse_dates=["date"])
    weekly = pd.read_csv(f"{DATA_DIR}/weekly.csv", parse_dates=["week_start"])
    inventory = pd.read_csv(f"{DATA_DIR}/inventory_snapshots.csv", parse_dates=["date"])
    forecast = pd.read_csv(f"{DATA_DIR}/production_forecast.csv", parse_dates=["week_start"])
    risk = pd.read_csv(f"{DATA_DIR}/risk_table.csv")
    with open(f"{DATA_DIR}/model_metrics.json") as f:
        metrics = json.load(f)

    sales_daily = sales_daily.merge(sku_master[["sku_id", "category", "description"]], on="sku_id", how="left")
    sales_daily["month"] = sales_daily["date"].dt.to_period("M").astype(str)
    sales_daily["month_num"] = sales_daily["date"].dt.month
    sales_daily["dow"] = sales_daily["date"].dt.day_name()

    latest_inv = inventory.sort_values("date").groupby("sku_id").tail(1).set_index("sku_id")
    risk = risk.merge(sku_master[["sku_id", "subcategory"]], on="sku_id", how="left")

    return dict(sales_daily=sales_daily, sku_master=sku_master, calendar=calendar_df,
                weekly=weekly, inventory=inventory, latest_inv=latest_inv,
                forecast=forecast, risk=risk, metrics=metrics)


DATA = load_data()
sales_daily = DATA["sales_daily"]
sku_master = DATA["sku_master"]
calendar_df = DATA["calendar"]
weekly = DATA["weekly"]
inventory = DATA["inventory"]
latest_inv = DATA["latest_inv"]
forecast = DATA["forecast"]
risk = DATA["risk"]
metrics = DATA["metrics"]

CATEGORIES = sorted(sku_master["category"].unique())


def money(x):
    return f"GBP {x:,.0f}"


def kpi_card(label, value, sub=""):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


def section(title):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def get_portfolio_filters():
    default_filters = {
        "date_range": (
            pd.Timestamp(metrics["data_date_range"][0]).date(),
            pd.Timestamp(metrics["data_date_range"][1]).date(),
        ),
        "categories": list(CATEGORIES),
        "quadrants": list(sorted(risk["quadrant"].unique())),
        "include_healthy": True,
    }
    return st.session_state.get("portfolio_filters", default_filters)


def apply_portfolio_filters(sales_df, risk_df, filters=None):
    filters = filters or get_portfolio_filters()
    sales_df = sales_df.copy()
    risk_df = risk_df.copy()

    start_date, end_date = filters["date_range"]
    sales_df = sales_df[(sales_df["date"] >= pd.Timestamp(start_date)) & (sales_df["date"] <= pd.Timestamp(end_date))]

    selected_categories = filters["categories"]
    if selected_categories:
        sales_df = sales_df[sales_df["category"].isin(selected_categories)]
        risk_df = risk_df[risk_df["category"].isin(selected_categories)]

    selected_quadrants = filters["quadrants"]
    if selected_quadrants:
        risk_df = risk_df[risk_df["quadrant"].isin(selected_quadrants)]

    if not filters["include_healthy"]:
        risk_df = risk_df[risk_df["quadrant"] != "Healthy"]

    return sales_df, risk_df


# --------------------------------------------------------------------------------------
# Sidebar navigation
# --------------------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🔮 FORESIGHT")
    st.caption("Demand & Inventory Intelligence — NorthBay Living")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["🏠 Home", "📊 Visualization Center", "📈 Sales Analytics", "🔮 Forecast", "📦 Inventory", "⚠️ Risk Dashboard",
         "🔍 Product Details", "📊 Executive Summary", "🎛️ What-If Simulator", "🔔 Alerts Center"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.subheader("Interactive filters")
    min_date = sales_daily["date"].min().date()
    max_date = sales_daily["date"].max().date()
    date_range = st.slider(
        "Date window",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date),
        format="YYYY-MM-DD",
    )
    categories = st.multiselect("Categories", CATEGORIES, default=CATEGORIES)
    quadrants = st.multiselect(
        "Risk quadrants",
        options=sorted(risk["quadrant"].unique()),
        default=sorted(risk["quadrant"].unique()),
    )
    include_healthy = st.checkbox("Include Healthy SKUs", value=True)
    st.session_state["portfolio_filters"] = {
        "date_range": date_range,
        "categories": categories,
        "quadrants": quadrants,
        "include_healthy": include_healthy,
    }
    if st.button("Reset filters"):
        st.session_state["portfolio_filters"] = {
            "date_range": (min_date, max_date),
            "categories": list(CATEGORIES),
            "quadrants": list(sorted(risk["quadrant"].unique())),
            "include_healthy": True,
        }
    st.markdown("---")
    st.caption(f"Data window: {metrics['data_date_range'][0]} to {metrics['data_date_range'][1]}")
    st.caption(f"{metrics['n_skus']} active SKUs · {metrics['horizon_weeks']}-week forecast horizon")


# ========================================================================================
# PAGE: HOME
# ========================================================================================
if page == "🏠 Home":
    filters = get_portfolio_filters()
    filtered_sales, filtered_risk = apply_portfolio_filters(sales_daily, risk, filters)

    st.markdown("# Welcome to FORESIGHT")
    st.markdown("""
    Your demand forecast and stockout/overstock early-warning system, built from NorthBay's
    own sales history. Use the sidebar to explore sales trends, the demand forecast, inventory
    risk, and individual products — or jump straight to **Executive Summary** for the headline
    numbers.
    """)

    total_revenue = filtered_sales["revenue"].sum()
    total_units = filtered_sales["units_sold"].sum()
    n_reorder = int((filtered_risk["quadrant"] == "Reorder Now").sum())
    n_markdown = int((filtered_risk["quadrant"] == "Markdown / Clear").sum())
    total_at_stake = filtered_risk["revenue_at_stake"].sum()

    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_card("Total Revenue (data window)", money(total_revenue), f"{total_units:,.0f} units sold")
    with c2: kpi_card("Active SKUs Tracked", f"{metrics['n_skus']}", "Top-200 by revenue")
    with c3: kpi_card("SKUs Needing Action", f"{n_reorder + n_markdown}", f"{n_reorder} reorder · {n_markdown} markdown")
    with c4: kpi_card("Rupee Value at Stake", money(total_at_stake), "Sales-at-risk + capital locked")

    st.write("")
    col1, col2 = st.columns([2, 1])
    with col1:
        section("Demand trend at a glance")
        wk_total = filtered_sales.copy()
        wk_total["week_start"] = wk_total["date"] - pd.to_timedelta(wk_total["date"].dt.weekday, unit="D")
        wk_total = wk_total.groupby("week_start")["units_sold"].sum().reset_index()
        fig = px.area(wk_total, x="week_start", y="units_sold", template=PLOTLY_TEMPLATE,
                       color_discrete_sequence=[BRAND_ACCENT])
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis_title="Units / week", xaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        section("Portfolio health")
        qcounts = filtered_risk["quadrant"].value_counts().reset_index()
        qcounts.columns = ["quadrant", "count"]
        fig = px.pie(qcounts, names="quadrant", values="count", hole=0.55, template=PLOTLY_TEMPLATE,
                     color="quadrant", color_discrete_map=COLOR_MAP)
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), showlegend=True,
                           legend=dict(orientation="h", y=-0.15))
        st.plotly_chart(fig, use_container_width=True)

    section("Top priority actions right now")
    top_actions = filtered_risk.sort_values("revenue_at_stake", ascending=False).head(5)
    for _, r in top_actions.iterrows():
        color = COLOR_MAP.get(r["quadrant"], "#999")
        st.markdown(f"""
        <div class="alert-card" style="border-left-color:{color};">
            <span class="badge" style="background:{color};">{r['quadrant']}</span>
            <b>{r['description']}</b> ({r['sku_id']}) — {r['recommended_action']}
            <br><span class="kpi-sub">Revenue at stake: {money(r['revenue_at_stake'])}</span>
        </div>
        """, unsafe_allow_html=True)


# ========================================================================================
# PAGE: VISUALIZATION CENTER
# ========================================================================================
elif page == "📊 Visualization Center":
    st.markdown("# 📊 Visualization Center")
    st.caption("Explore demand, sales, inventory and product patterns.")
    st.markdown("---")

    base_df = sales_daily.copy()
    if "category" not in base_df.columns:
        base_df = base_df.merge(sku_master[["sku_id", "category"]], on="sku_id", how="left")
    base_df = base_df.merge(calendar_df[["date", "season", "promo_event"]], on="date", how="left")
    base_df = base_df.merge(
        latest_inv.reset_index()[["sku_id", "on_hand_units", "on_order_units", "lead_time_days", "reorder_point"]],
        on="sku_id",
        how="left",
    )
    if "category" in base_df.columns:
        base_df["category"] = base_df["category"].fillna("Unknown")

    st.markdown("### 🔎 Filters")
    category_options = sorted(base_df["category"].dropna().unique())
    selected_categories = st.multiselect("Category", category_options, default=category_options)
    sku_options = ["All"] + [f"{row['sku_id']} — {row['description']}" for _, row in sku_master.sort_values("description")[['sku_id','description']].drop_duplicates().iterrows()]
    selected_sku = st.selectbox("SKU", sku_options, index=0)
    date_min = base_df["date"].min().date()
    date_max = base_df["date"].max().date()
    selected_dates = st.slider("Date Range", min_value=date_min, max_value=date_max, value=(date_min, date_max))
    season_options = sorted(base_df["season"].dropna().unique())
    selected_seasons = st.multiselect("Season", season_options, default=season_options)
    promo_options = [0, 1]
    selected_promo = st.multiselect("Promotion", promo_options, default=promo_options)

    filtered_df = base_df.copy()
    filtered_df = filtered_df[(filtered_df["date"] >= pd.Timestamp(selected_dates[0])) & (filtered_df["date"] <= pd.Timestamp(selected_dates[1]))]
    if selected_categories:
        filtered_df = filtered_df[filtered_df["category"].isin(selected_categories)]
    if selected_seasons:
        filtered_df = filtered_df[filtered_df["season"].isin(selected_seasons)]
    if selected_promo:
        filtered_df = filtered_df[filtered_df["promo_flag"].isin(selected_promo)]
    if selected_sku != "All":
        sku_id = selected_sku.split(" — ", 1)[0]
        filtered_df = filtered_df[filtered_df["sku_id"] == sku_id]

    st.markdown("### 📈 Select Visualization")
    viz_options = [
        "Bar Chart",
        "Line Chart",
        "Area Chart",
        "Pie Chart",
        "Donut Chart",
        "Scatter Plot",
        "Histogram",
        "Box Plot",
        "Violin Plot",
        "Correlation Heatmap",
        "Treemap",
        "Sunburst Chart",
        "Radar Chart",
        "Bubble Chart",
        "Pair Plot",
    ]
    selected_viz = st.selectbox("Select Visualization", viz_options, index=0)
    st.markdown("---")
    st.markdown("### Selected Chart")

    chart_data = filtered_df.copy()
    default_group = "category"

    if selected_viz == "Bar Chart":
        metric = st.selectbox("Metric", ["units_sold", "revenue", "on_hand_units"], index=0)
        if metric == "on_hand_units":
            grp = chart_data.groupby("category", as_index=False)["on_hand_units"].sum().sort_values("on_hand_units", ascending=False)
        else:
            grp = chart_data.groupby(default_group, as_index=False)[metric].sum().sort_values(metric, ascending=False)
        fig = px.bar(grp, x=default_group, y=metric, color=default_group, template=PLOTLY_TEMPLATE,
                     title=f"{metric.replace('_', ' ').title()} by {default_group.title()}")
    elif selected_viz == "Line Chart":
        metric = st.selectbox("Metric", ["units_sold", "revenue"], index=0)
        line_df = chart_data.groupby("date", as_index=False)[metric].sum().sort_values("date")
        fig = px.line(line_df, x="date", y=metric, markers=True, template=PLOTLY_TEMPLATE,
                      title=f"{metric.replace('_', ' ').title()} over time")
    elif selected_viz == "Area Chart":
        metric = st.selectbox("Metric", ["units_sold", "revenue"], index=0)
        area_df = chart_data.groupby("date", as_index=False)[metric].sum().sort_values("date")
        area_df["cum"] = area_df[metric].cumsum()
        fig = px.area(area_df, x="date", y="cum", template=PLOTLY_TEMPLATE,
                      title=f"Cumulative {metric.replace('_', ' ').title()} over time")
    elif selected_viz == "Pie Chart":
        pie_df = chart_data.groupby("category", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
        fig = px.pie(pie_df, names="category", values="revenue", hole=0, template=PLOTLY_TEMPLATE,
                     title="Category share of total revenue")
    elif selected_viz == "Donut Chart":
        donut_df = chart_data.groupby("category", as_index=False)["units_sold"].sum().sort_values("units_sold", ascending=False)
        fig = px.pie(donut_df, names="category", values="units_sold", hole=0.5, template=PLOTLY_TEMPLATE,
                     title="Category share of total units sold")
    elif selected_viz == "Scatter Plot":
        fig = px.scatter(chart_data, x="unit_price", y="units_sold", color="category", hover_name="description",
                         template=PLOTLY_TEMPLATE, title="Unit Price vs Units Sold")
    elif selected_viz == "Histogram":
        hist_metric = st.selectbox("Histogram metric", ["units_sold", "revenue", "unit_price"], index=0)
        fig = px.histogram(chart_data, x=hist_metric, nbins=30, template=PLOTLY_TEMPLATE,
                           title=f"Distribution of {hist_metric.replace('_', ' ').title()}")
    elif selected_viz == "Box Plot":
        fig = px.box(chart_data, x="category", y="units_sold", color="category", template=PLOTLY_TEMPLATE,
                     title="Demand distribution by category")
    elif selected_viz == "Violin Plot":
        fig = px.violin(chart_data, x="category", y="revenue", color="category", box=True, template=PLOTLY_TEMPLATE,
                        title="Revenue distribution by category")
    elif selected_viz == "Correlation Heatmap":
        corr_df = chart_data[["units_sold", "revenue", "unit_price", "lead_time_days", "on_hand_units", "reorder_point"]].dropna()
        corr = corr_df.corr(numeric_only=True)
        fig = px.imshow(corr, text_auto=True, color_continuous_scale="Purples", template=PLOTLY_TEMPLATE,
                        title="Correlation Heatmap")
    elif selected_viz == "Treemap":
        treemap_df = chart_data.groupby(["category", "sku_id", "description"], as_index=False)["revenue"].sum()
        fig = px.treemap(treemap_df, path=["category", "description"], values="revenue", color="revenue",
                         color_continuous_scale="Purples", template=PLOTLY_TEMPLATE,
                         title="Category → SKU revenue contribution")
    elif selected_viz == "Sunburst Chart":
        sun_df = chart_data.groupby(["category", "description"], as_index=False)["units_sold"].sum()
        fig = px.sunburst(sun_df, path=["category", "description"], values="units_sold", color="units_sold",
                          color_continuous_scale="Blues", template=PLOTLY_TEMPLATE,
                          title="Category → SKU demand contribution")
    elif selected_viz == "Radar Chart":
        radar_skus = st.multiselect("Choose 2–4 SKUs to compare", options=sorted(chart_data["sku_id"].unique()), default=list(sorted(chart_data["sku_id"].unique()))[:min(3, len(chart_data["sku_id"].unique()))])
        if radar_skus:
            radar_df = risk[risk["sku_id"].isin(radar_skus)][["sku_id", "description", "stockout_risk", "overstock_risk", "list_price", "unit_cost", "sales_at_risk_rupees", "capital_locked_rupees"]].copy()
            if radar_df.empty:
                st.info("No risk data for the selected SKUs.")
                st.stop()
            radar_df["avg_price"] = radar_df["list_price"]
            radar_df["avg_cost"] = radar_df["unit_cost"]
            metrics_list = ["stockout_risk", "overstock_risk", "list_price", "unit_cost", "sales_at_risk_rupees", "capital_locked_rupees"]
            theta = ["Stockout Risk", "Overstock Risk", "List Price", "Unit Cost", "Sales at Risk", "Capital Locked"]
            fig = go.Figure()
            for _, row in radar_df.iterrows():
                vals = [row[m] for m in metrics_list]
                fig.add_trace(go.Scatterpolar(r=vals, theta=theta, fill="toself", name=row["description"]))
            fig.update_layout(template=PLOTLY_TEMPLATE, title="SKU KPI comparison (Radar)")
        else:
            fig = go.Figure()
            st.info("Choose at least one SKU to compare.")
    elif selected_viz == "Bubble Chart":
        agg_df = chart_data.groupby(["sku_id", "description", "category"], as_index=False).agg(
            revenue=("revenue", "sum"),
            units_sold=("units_sold", "sum"),
            unit_price=("unit_price", "mean"),
        )
        fig = px.scatter(agg_df, x="unit_price", y="revenue", size="units_sold", color="category",
                         hover_name="description", template=PLOTLY_TEMPLATE,
                         title="Price vs Revenue with bubble size = units sold")
    elif selected_viz == "Pair Plot":
        pair_df = chart_data[["units_sold", "revenue", "unit_price", "lead_time_days", "on_hand_units"]].dropna()
        fig = px.scatter_matrix(pair_df, dimensions=["units_sold", "revenue", "unit_price", "lead_time_days", "on_hand_units"], template=PLOTLY_TEMPLATE,
                                title="Pair Plot of key numeric variables")

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown("### 📌 Chart Insights")
    insights = []
    if selected_viz in ["Bar Chart", "Pie Chart", "Donut Chart"]:
        if selected_viz == "Bar Chart":
            metric = st.session_state.get("bar_metric", "units_sold")
        else:
            metric = "revenue" if selected_viz == "Pie Chart" else "units_sold"
        if metric == "on_hand_units":
            comp = chart_data.groupby("category", as_index=False)["on_hand_units"].sum().sort_values("on_hand_units", ascending=False)
        else:
            comp = chart_data.groupby("category", as_index=False)[metric].sum().sort_values(metric, ascending=False)
        if not comp.empty:
            top = comp.iloc[0]
            insights.append(f"{top['category']} leads the filtered view with {top[metric]:,.0f} {metric.replace('_', ' ')}.")
            if len(comp) > 1:
                second = comp.iloc[1]
                insights.append(f"{second['category']} ranks second, trailing by {top[metric] - second[metric]:,.0f}.")
    elif selected_viz == "Line Chart":
        line_df = chart_data.groupby("date", as_index=False)["units_sold"].sum().sort_values("date")
        if not line_df.empty:
            peak = line_df.nlargest(1, "units_sold").iloc[0]
            insights.append(f"The highest demand point in the current date window is {peak['date'].strftime('%Y-%m-%d')} with {peak['units_sold']:,.0f} units sold.")
            slope = line_df["units_sold"].pct_change().fillna(0).mean()
            insights.append(f"Average relative weekly change in the filtered view is about {slope * 100:.1f}%.")
    elif selected_viz == "Area Chart":
        area_df = chart_data.groupby("date", as_index=False)["revenue"].sum().sort_values("date")
        if not area_df.empty:
            insights.append(f"Cumulative revenue in the current window reaches {area_df['revenue'].sum():,.0f} across {len(area_df)} dates.")
            peak = area_df.nlargest(1, "revenue").iloc[0]
            insights.append(f"The strongest revenue day is {peak['date'].strftime('%Y-%m-%d')} at {peak['revenue']:,.0f}.")
    elif selected_viz in ["Scatter Plot", "Bubble Chart"]:
        if selected_viz == "Scatter Plot":
            xcol, ycol = "unit_price", "units_sold"
        else:
            xcol, ycol = "unit_price", "revenue"
        corr = chart_data[[xcol, ycol]].dropna().corr().iloc[0, 1]
        insights.append(f"The relationship between {xcol.replace('_', ' ')} and {ycol.replace('_', ' ')} has a correlation of {corr:.2f}.")
        top = chart_data.nlargest(1, ycol).iloc[0]
        insights.append(f"The strongest observation is {top['description']} with {top[ycol]:,.0f} {ycol.replace('_', ' ')}.")
    elif selected_viz == "Histogram":
        metric = st.session_state.get("hist_metric", "units_sold")
        avg = chart_data[metric].mean()
        insights.append(f"The average {metric.replace('_', ' ')} in the filtered data is {avg:,.1f}.")
        insights.append(f"The median {metric.replace('_', ' ')} is {chart_data[metric].median():,.1f}.")
    elif selected_viz in ["Box Plot", "Violin Plot"]:
        metric = "units_sold" if selected_viz == "Box Plot" else "revenue"
        top = chart_data.groupby("category", as_index=False)[metric].mean().sort_values(metric, ascending=False).iloc[0]
        insights.append(f"{top['category']} has the highest average {metric.replace('_', ' ')} in the filtered range.")
        insights.append(f"The filtered dataset includes {chart_data['category'].nunique()} categories with a wide spread in demand.")
    elif selected_viz == "Correlation Heatmap":
        corr_df = chart_data[["units_sold", "revenue", "unit_price", "lead_time_days", "on_hand_units", "reorder_point"]].dropna().corr(numeric_only=True)
        strongest = corr_df.abs().where(~np.eye(len(corr_df), dtype=bool)).stack().sort_values(ascending=False).iloc[0]
        insights.append(f"The strongest pairwise relationship among the selected numeric fields is {strongest:.2f}.")
        highest = corr_df["revenue"].drop(labels="revenue").abs().idxmax(), corr_df["revenue"].drop(labels="revenue").abs().max()
        insights.append(f"Revenue is most closely associated with {highest[0]} (absolute correlation {highest[1]:.2f}).")
    elif selected_viz in ["Treemap", "Sunburst Chart"]:
        if selected_viz == "Treemap":
            comp = chart_data.groupby("category", as_index=False)["revenue"].sum().sort_values("revenue", ascending=False)
        else:
            comp = chart_data.groupby("category", as_index=False)["units_sold"].sum().sort_values("units_sold", ascending=False)
        total = comp.iloc[:,1].sum()
        top = comp.iloc[0]
        insights.append(f"{top['category']} contributes {top.iloc[1] / total * 100:.1f}% of the current filtered total.")
        insights.append(f"The current split is based on {len(comp)} categories in the active filter window.")
    elif selected_viz == "Radar Chart":
        if 'radar_df' in locals() and not radar_df.empty:
            top = radar_df.nlargest(1, "sales_at_risk_rupees").iloc[0]
            insights.append(f"{top['description']} shows the highest sales-at-risk value in the selected comparison set.")
            insights.append(f"The selected comparison set spans {radar_df['sku_id'].nunique()} SKUs with distinct KPI profiles.")
    elif selected_viz == "Pair Plot":
        pair_corr = chart_data[["units_sold", "revenue", "unit_price", "lead_time_days", "on_hand_units"]].dropna().corr().round(2)
        strongest = pair_corr.abs().where(~np.eye(len(pair_corr), dtype=bool)).stack().sort_values(ascending=False).iloc[0]
        insights.append(f"The strongest pairwise pattern in the multi-variable view has a correlation of {strongest:.2f}.")
        insights.append(f"This view covers {pair_corr.shape[0]} numeric fields from the filtered dataset.")

    for insight in insights[:4]:
        st.markdown(f"• {insight}")

# ========================================================================================
# PAGE: SALES ANALYTICS
# ========================================================================================
elif page == "📈 Sales Analytics":
    filters = get_portfolio_filters()
    filtered_sales, _ = apply_portfolio_filters(sales_daily, risk, filters)

    st.markdown("# Sales Analytics")
    st.caption("Chart types on this page: area, line, bar, box plot, treemap, heatmap")

    colf1, colf2 = st.columns([1, 3])
    with colf1:
        cat_filter = st.multiselect("Filter by category", CATEGORIES, default=filters["categories"])
    sd = filtered_sales if not cat_filter else filtered_sales[filtered_sales["category"].isin(cat_filter)]

    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("Revenue (filtered)", money(sd["revenue"].sum()))
    with c2: kpi_card("Units sold (filtered)", f"{sd['units_sold'].sum():,.0f}")
    with c3: kpi_card("Avg daily revenue", money(sd.groupby('date')['revenue'].sum().mean()))

    tab1, tab2, tab3 = st.tabs(["Trend", "Category & Price Mix", "Seasonality Heatmap"])

    with tab1:
        gran = st.radio("Granularity", ["Daily", "Weekly"], horizontal=True)
        if gran == "Daily":
            trend = sd.groupby("date")[["units_sold", "revenue"]].sum().reset_index()
            xcol = "date"
        else:
            sd2 = sd.copy()
            sd2["week_start"] = sd2["date"] - pd.to_timedelta(sd2["date"].dt.weekday, unit="D")
            trend = sd2.groupby("week_start")[["units_sold", "revenue"]].sum().reset_index()
            xcol = "week_start"
        fig = px.line(trend, x=xcol, y="units_sold", template=PLOTLY_TEMPLATE,
                       color_discrete_sequence=[BRAND_PRIMARY], title="Units sold over time")
        st.plotly_chart(fig, use_container_width=True)

        trend["cum_revenue"] = trend["revenue"].cumsum()
        fig2 = px.area(trend, x=xcol, y="cum_revenue", template=PLOTLY_TEMPLATE,
                        color_discrete_sequence=[BRAND_ACCENT], title="Cumulative revenue")
        st.plotly_chart(fig2, use_container_width=True)

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            cat_rev = sd.groupby("category")["revenue"].sum().sort_values(ascending=False).reset_index()
            fig = px.bar(cat_rev, x="revenue", y="category", orientation="h", template=PLOTLY_TEMPLATE,
                         color_discrete_sequence=[BRAND_PRIMARY], title="Revenue by category")
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = px.box(sd, x="category", y="unit_price", template=PLOTLY_TEMPLATE,
                         color="category", title="Price distribution by category")
            fig.update_layout(showlegend=False)
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

        tm = sd.groupby(["category", "sku_id", "description"])["revenue"].sum().reset_index()
        fig = px.treemap(tm, path=["category", "description"], values="revenue",
                          color="revenue", color_continuous_scale="Purples", template=PLOTLY_TEMPLATE,
                          title="Revenue concentration: category -> SKU")
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        heat = sd.groupby(["month_num", "dow"])["units_sold"].mean().reset_index()
        heat_p = heat.pivot(index="dow", columns="month_num", values="units_sold").reindex(dow_order)
        fig = go.Figure(data=go.Heatmap(z=heat_p.values, x=[calmod.month_abbr[m] for m in heat_p.columns],
                                         y=heat_p.index, colorscale="Purples"))
        fig.update_layout(title="Average daily demand by day-of-week x month", template=PLOTLY_TEMPLATE)
        st.plotly_chart(fig, use_container_width=True)


# ========================================================================================
# PAGE: FORECAST
# ========================================================================================
elif page == "🔮 Forecast":
    st.markdown("# Demand Forecast")
    st.caption("Chart types on this page: line (actual vs. forecast), bar (model comparison)")

    section("Model performance (backtested, honestly)")
    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("Baseline WAPE (seasonal-naive)", f"{metrics['avg_baseline_wape']:.3f}", "3-fold rolling-origin backtest")
    with c2: kpi_card("LightGBM WAPE (production model)", f"{metrics['avg_lgbm_wape']:.3f}",
                       f"{100*(metrics['avg_baseline_wape']-metrics['avg_lgbm_wape'])/metrics['avg_baseline_wape']:.1f}% better than baseline")
    with c3: kpi_card("Prophet WAPE (top-15 SKUs)", f"{metrics['prophet_wape_top15']:.3f}", "LightGBM still wins on same subset")

    comp = pd.DataFrame({
        "Model": ["Seasonal-naive (baseline)", "Prophet (top-15 subset)", "LightGBM (production)"],
        "WAPE": [metrics["avg_baseline_wape"], metrics["prophet_wape_top15"], metrics["avg_lgbm_wape"]],
    })
    fig = px.bar(comp, x="WAPE", y="Model", orientation="h", template=PLOTLY_TEMPLATE,
                 color="Model", color_discrete_sequence=["#B0AED0", "#8B85D6", BRAND_PRIMARY],
                 title="Model comparison — lower WAPE is better")
    fig.update_layout(showlegend=False, height=280)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    section("Forecast explorer — actual history vs. next 8-week forecast")
    sku_options = sku_master.sort_values("description")["sku_id"] + " — " + sku_master.sort_values("description")["description"]
    sku_lookup = dict(zip(sku_options, sku_master.sort_values("description")["sku_id"]))
    choice = st.selectbox("Choose a SKU", list(sku_lookup.keys()))
    sku_id = sku_lookup[choice]

    hist = weekly[weekly["sku_id"] == sku_id].sort_values("week_start").tail(30)
    fut = forecast[forecast["sku_id"] == sku_id].sort_values("week_start")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hist["week_start"], y=hist["units_sold"], mode="lines+markers",
                              name="Actual", line=dict(color=BRAND_PRIMARY, width=2)))
    fig.add_trace(go.Scatter(x=fut["week_start"], y=fut["pred"], mode="lines+markers",
                              name="Forecast (next 8 weeks)", line=dict(color=BRAND_ACCENT, width=2, dash="dash")))
    fig.update_layout(title=f"{choice} — weekly demand", template=PLOTLY_TEMPLATE, height=420,
                       xaxis_title="", yaxis_title="Units / week")
    st.plotly_chart(fig, use_container_width=True)

    st.info(
        "WAPE in the 0.6-0.8 range means this forecast is directionally useful and clearly "
        "beats guessing, but isn't precise at the single-SKU-week level — best used to "
        "prioritise which SKUs need attention, not to set exact order quantities."
    )


# ========================================================================================
# PAGE: INVENTORY
# ========================================================================================
elif page == "📦 Inventory":
    st.markdown("# Inventory Dashboard")
    st.caption("Chart types on this page: bar, scatter, 3D scatter")
    st.warning(
        "Inventory position is **simulated** (no real inventory feed was in the source data) — "
        "connect NorthBay's real inventory system before using this for live decisions.",
        icon="⚠️",
    )

    colf1, colf2 = st.columns([1, 3])
    with colf1:
        cat_filter = st.multiselect("Filter by category", CATEGORIES, default=[], key="inv_cat")
    inv_view = latest_inv.join(sku_master.set_index("sku_id")[["description", "category"]])
    if cat_filter:
        inv_view = inv_view[inv_view["category"].isin(cat_filter)]

    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("Total units on hand", f"{inv_view['on_hand_units'].sum():,.0f}")
    with c2: kpi_card("Total units on order", f"{inv_view['on_order_units'].sum():,.0f}")
    with c3: kpi_card("Avg lead time", f"{inv_view['lead_time_days'].mean():.1f} days")

    section("On-hand stock vs. reorder point (lowest coverage first)")
    inv_view = inv_view.reset_index().rename(columns={"index": "sku_id"})
    inv_view["coverage_ratio"] = inv_view["on_hand_units"] / inv_view["reorder_point"].replace(0, np.nan)
    show = inv_view.sort_values("coverage_ratio").head(20)
    fig = go.Figure()
    fig.add_trace(go.Bar(y=show["description"], x=show["on_hand_units"], name="On hand",
                          orientation="h", marker_color=BRAND_ACCENT))
    fig.add_trace(go.Bar(y=show["description"], x=show["reorder_point"], name="Reorder point",
                          orientation="h", marker_color="#D9534F", opacity=0.55))
    fig.update_layout(barmode="overlay", template=PLOTLY_TEMPLATE, height=560,
                       title="20 SKUs closest to (or below) their reorder point",
                       yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        fig = px.scatter(inv_view, x="lead_time_days", y="reorder_point", color="category",
                          size="on_hand_units", hover_name="description", template=PLOTLY_TEMPLATE,
                          title="Lead time vs. reorder point (bubble = on-hand units)")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        merged3d = inv_view.merge(risk[["sku_id", "stockout_risk", "overstock_risk"]], on="sku_id", how="left")
        fig = px.scatter_3d(merged3d, x="on_hand_units", y="lead_time_days", z="reorder_point",
                             color="category", hover_name="description", template=PLOTLY_TEMPLATE,
                             title="Inventory position in 3D")
        st.plotly_chart(fig, use_container_width=True)


# ========================================================================================
# PAGE: RISK DASHBOARD
# ========================================================================================
elif page == "⚠️ Risk Dashboard":
    filters = get_portfolio_filters()
    filtered_sales, filtered_risk = apply_portfolio_filters(sales_daily, risk, filters)

    def risk_severity(row):
        q = row["quadrant"]
        if q == "Reorder Now":
            return "Critical" if row["stockout_risk"] >= 0.5 else "High"
        if q == "Markdown / Clear":
            return "High" if row["overstock_risk"] >= 0.5 else "Medium"
        if q == "Watch / Volatile":
            return "Medium" if (row["stockout_risk"] + row["overstock_risk"]) / 2 >= 0.35 else "Low"
        return "Low"

    severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    rv = filtered_risk.copy()
    rv["severity"] = rv.apply(risk_severity, axis=1)

    st.markdown("# Risk Dashboard")
    st.caption("Interactive risk-management decision system — use the filters and charts together to prioritise action.")

    c1, c2, c3, c4 = st.columns(4)
    reorder_df = rv[rv["quadrant"] == "Reorder Now"]
    markdown_df = rv[rv["quadrant"] == "Markdown / Clear"]
    with c1:
        tooltip = f"Affected SKUs: {len(reorder_df):,}\nExpected demand: {reorder_df['forecast_demand_leadtime'].sum():,.0f}\nAvg. stockout risk: {reorder_df['stockout_risk'].mean()*100:.1f}%"
        kpi_card("🔴 Reorder Now", f"{len(reorder_df):,}", f"{reorder_df['forecast_demand_leadtime'].sum():,.0f} units at risk")
        st.caption(f"<span title=\"{tooltip}\">Hover info</span>", unsafe_allow_html=True)
    with c2:
        tooltip = f"Affected SKUs: {len(markdown_df):,}\nOverstock exposure: {markdown_df['forecast_demand_horizon'].sum():,.0f}\nCapital tied: {money(markdown_df['capital_locked_rupees'].sum())}"
        kpi_card("🟠 Markdown / Clear", f"{len(markdown_df):,}", f"{money(markdown_df['capital_locked_rupees'].sum())} locked")
        st.caption(f"<span title=\"{tooltip}\">Hover info</span>", unsafe_allow_html=True)
    with c3:
        kpi_card("💰 Sales at Risk", money(rv["sales_at_risk_rupees"].sum()), f"{len(rv[rv['sales_at_risk_rupees'] > 0]):,} SKUs affected")
    with c4:
        kpi_card("💵 Capital Locked", money(rv["capital_locked_rupees"].sum()), f"{len(rv[rv['capital_locked_rupees'] > 0]):,} SKUs affected")

    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        q_filter = st.multiselect("Filter by quadrant", sorted(rv["quadrant"].unique()), default=sorted(rv["quadrant"].unique()), key="risk_quadrant_filter")
    with col2:
        cat_filter = st.multiselect("Filter by category", sorted(CATEGORIES), default=sorted(CATEGORIES), key="risk_category_filter")
    with col3:
        severity_filter = st.selectbox("Risk Severity", ["All", "Critical", "High", "Medium", "Low"], index=0)

    st.markdown("### 🔄 Reset Dashboard")
    if st.button("Reset filters"):
        st.session_state.pop("risk_quadrant_filter", None)
        st.session_state.pop("risk_category_filter", None)
        st.session_state.pop("risk_selected_sku", None)
        st.session_state.pop("risk_category_focus", None)
        st.session_state.pop("risk_quadrant_focus", None)
        st.rerun()

    rv = rv[rv["quadrant"].isin(q_filter)]
    rv = rv[rv["category"].isin(cat_filter)]
    if severity_filter != "All":
        rv = rv[rv["severity"] == severity_filter]

    if rv.empty:
        st.warning("No records match the selected filters. Reset the dashboard or relax the filters.")
        st.stop()

    col1, col2 = st.columns([2, 1])
    with col1:
        section("🎯 Risk Overview")
        fig = px.scatter(rv, x="overstock_risk", y="stockout_risk", size="revenue_at_stake",
                        color="quadrant", color_discrete_map=COLOR_MAP, hover_name="description",
                        size_max=45, template=PLOTLY_TEMPLATE)
        fig.add_vline(x=0.5, line_dash="dash", line_color="gray")
        fig.add_hline(y=0.5, line_dash="dash", line_color="gray")
        fig.update_layout(height=460, xaxis_range=[-0.02, 1.02], yaxis_range=[-0.02, 1.02],
                         xaxis_title="Overstock risk", yaxis_title="Stockout risk")
        fig.update_traces(
            customdata=rv[["sku_id", "description", "category", "sales_at_risk_rupees", "capital_locked_rupees", "recommended_action"]].values,
            hovertemplate="SKU: %{customdata[0]}<br>Description: %{customdata[1]}<br>Category: %{customdata[2]}<br>Stockout risk: %{y:.2%}<br>Overstock risk: %{x:.2%}<br>Sales at risk: GBP %{customdata[3]:,.0f}<br>Capital locked: GBP %{customdata[4]:,.0f}<br>Quadrant: %{marker.color}<br>Recommendation: %{customdata[5]}<extra></extra>")
        fig.update_layout(legend_title_text="Quadrant")
        plotly_kwargs = {"use_container_width": True}
        if "on_select" in inspect.signature(st.plotly_chart).parameters:
            plotly_kwargs["on_select"] = "rerun"
            plotly_kwargs["selection_mode"] = "points"
        st.plotly_chart(fig, **plotly_kwargs)

        coa = st.selectbox("Selected SKU", [f"{row['sku_id']} — {row['description']}" for _, row in rv.sort_values("revenue_at_stake", ascending=False).iterrows()], index=0)
        selected_sku_id = coa.split(" — ", 1)[0]
        st.session_state["risk_selected_sku"] = selected_sku_id
        if st.button("🔎 View SKU Details"):
            st.session_state["product_details_sku"] = selected_sku_id
            st.info(f"Selected SKU: {selected_sku_id}. Use the Product Details page to inspect this item.")
    with col2:
        section("Quadrant mix")
        qcounts = rv["quadrant"].value_counts().reset_index()
        qcounts.columns = ["quadrant", "count"]
        fig = px.pie(qcounts, names="quadrant", values="count", hole=0.55, color="quadrant",
                     color_discrete_map=COLOR_MAP, template=PLOTLY_TEMPLATE)
        fig.update_layout(height=460, legend=dict(orientation="h", y=-0.1))
        st.plotly_chart(fig, use_container_width=True)
        if len(rv) > 0:
            st.caption(f"Current filtered view: {len(rv)} SKUs · {rv['revenue_at_stake'].sum():,.0f} GBP at stake")

    c1, c2 = st.columns(2)
    with c1:
        section("💰 Financial Impact")
        metric_choice = st.selectbox("Metric", ["Sales at Risk", "Capital Locked"], index=0, key="risk_metric_select")
        impact_df = rv.groupby("category").agg(
            sales_at_risk=("sales_at_risk_rupees", "sum"),
            capital_locked=("capital_locked_rupees", "sum"),
            sku_count=("sku_id", "nunique"),
        ).reset_index()
        impact_df = impact_df.sort_values(metric_choice.lower().replace(" ", "_") if metric_choice == "Sales at Risk" else "capital_locked", ascending=False)
        fig = go.Figure(go.Waterfall(
            x=list(impact_df["category"]) + ["Total"],
            y=list(impact_df["sales_at_risk" if metric_choice == "Sales at Risk" else "capital_locked"]) + [None],
            measure=["relative"] * len(impact_df) + ["total"],
            decreasing={"marker": {"color": "#4CAF50"}}, increasing={"marker": {"color": "#D9534F"}},
            totals={"marker": {"color": BRAND_PRIMARY}},
        ))
        fig.update_layout(template=PLOTLY_TEMPLATE, height=400)
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        section("Portfolio funnel")
        funnel_df = pd.DataFrame({
            "stage": ["All active SKUs", "Flagged (any risk)", "Reorder Now", "Markdown / Clear"],
            "count": [len(filtered_risk), int((filtered_risk['quadrant'] != 'Healthy').sum()),
                      int((filtered_risk['quadrant'] == 'Reorder Now').sum()), int((filtered_risk['quadrant'] == 'Markdown / Clear').sum())],
        })
        fig = px.funnel(funnel_df, x="count", y="stage", template=PLOTLY_TEMPLATE,
                        color_discrete_sequence=[BRAND_PRIMARY])
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    selected_sku = st.session_state.get("risk_selected_sku")
    selected_row = rv[rv["sku_id"] == selected_sku].iloc[0] if selected_sku and (rv["sku_id"] == selected_sku).any() else rv.sort_values("revenue_at_stake", ascending=False).iloc[0]

    col1, col2 = st.columns([1.4, 1.2])
    with col1:
        section("⚠️ Selected Risk")
        st.markdown(f"**SKU:** {selected_row['sku_id']} — {selected_row['description']}\n**Category:** {selected_row['category']}\n**Quadrant:** {selected_row['quadrant']}\n**Recommended action:** {selected_row['recommended_action']}")
        st.metric("Sales at risk", money(selected_row['sales_at_risk_rupees']))
        st.metric("Capital locked", money(selected_row['capital_locked_rupees']))
    with col2:
        section("Why is this SKU at risk?")
        st.write("**Stockout Risk**")
        st.progress(float(selected_row['stockout_risk']))
        st.caption(f"{selected_row['stockout_risk'] * 100:.1f}%")
        st.write("Main drivers:")
        drivers = []
        if selected_row['stockout_risk'] >= 0.5:
            drivers.append("- High stockout risk relative to lead-time demand")
        if selected_row['lead_time_days'] >= 10:
            drivers.append("- Longer lead time reduces inventory coverage")
        if selected_row['forecast_demand_leadtime'] > selected_row['on_hand_units'] + selected_row['on_order_units']:
            drivers.append("- Forecast demand over lead time exceeds available stock")
        if not drivers:
            drivers.append("- Risk is modest and driven by normal portfolio variability")
        for d in drivers:
            st.markdown(d)

        st.write("**Overstock Risk**")
        st.progress(float(selected_row['overstock_risk']))
        st.caption(f"{selected_row['overstock_risk'] * 100:.1f}%")
        st.write("Main drivers:")
        over_drivers = []
        if selected_row['overstock_risk'] >= 0.5:
            over_drivers.append("- Inventory exceeds expected near-term demand")
        if selected_row['capital_locked_rupees'] > 0:
            over_drivers.append("- Capital is tied in excess stock")
        if selected_row['on_hand_units'] > selected_row['reorder_point']:
            over_drivers.append("- Current on-hand stock sits above reorder coverage")
        if not over_drivers:
            over_drivers.append("- No significant excess inventory signal in current data")
        for d in over_drivers:
            st.markdown(d)

    st.markdown("### 🎯 Recommended Action")
    st.info(f"**{selected_row['quadrant']}**\nWhy: {selected_row['recommended_action']}\nPriority: {('High' if selected_row['quadrant'] == 'Reorder Now' else 'Medium' if selected_row['quadrant'] == 'Watch / Volatile' else 'Low' if selected_row['quadrant'] == 'Healthy' else 'High')}\nSales at Risk: {money(selected_row['sales_at_risk_rupees'])}\nCapital Locked: {money(selected_row['capital_locked_rupees'])}\nSuggested next step: {selected_row['recommended_action']}")

    st.markdown("---")
    section("📋 Prioritised Action List")
    show_cols = ["sku_id", "description", "category", "quadrant", "stockout_risk", "overstock_risk",
                 "sales_at_risk_rupees", "capital_locked_rupees", "revenue_at_stake", "recommended_action"]
    action_df = rv.sort_values("revenue_at_stake", ascending=False)[show_cols].copy()
    for col in ["stockout_risk", "overstock_risk"]:
        action_df[col] = action_df[col].round(3)
    st.dataframe(
        action_df,
        use_container_width=True,
        height=370,
        column_config={
            "stockout_risk": st.column_config.ProgressColumn("Stockout risk", min_value=0, max_value=1),
            "overstock_risk": st.column_config.ProgressColumn("Overstock risk", min_value=0, max_value=1),
            "sales_at_risk_rupees": st.column_config.NumberColumn("Sales at risk", format="GBP %.0f"),
            "capital_locked_rupees": st.column_config.NumberColumn("Capital locked", format="GBP %.0f"),
            "revenue_at_stake": st.column_config.NumberColumn("Total at stake", format="GBP %.0f"),
        },
    )
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("📥 Download Current Filtered Risk List", rv.to_csv(index=False).encode(), "foresight_filtered_risk_list.csv", "text/csv")
    with c2:
        selected_download = pd.DataFrame([selected_row])
        st.download_button("📥 Download Selected SKU Risk Details", selected_download.to_csv(index=False).encode(), f"risk_{selected_row['sku_id']}.csv", "text/csv")

    st.caption("Severity mapping: Critical = Reorder Now with high stockout pressure; High = markdown or reorder cases with strong exposure; Medium = elevated volatility; Low = healthy or low-risk items. This uses the project’s existing risk values and quadrant logic.")


# ========================================================================================
# PAGE: PRODUCT DETAILS
# ========================================================================================
elif page == "🔍 Product Details":
    st.markdown("# Product Details")
    st.caption("Interactive product intelligence for demand, inventory, and risk.")

    def product_kpi_card(label, value, details, tooltip=""):
        st.markdown(
            f"""
            <div class="kpi-card" title="{tooltip}">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
                <div class="kpi-sub">{details}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    @st.cache_data
    def get_product_options(filtered_sales, filtered_risk, sku_master_df):
        eligible = sorted(set(filtered_sales["sku_id"].unique()).union(filtered_risk["sku_id"].unique()))
        product_rows = []
        for sku in eligible:
            match = sku_master_df[sku_master_df["sku_id"] == sku]
            if match.empty:
                continue
            row = match.iloc[0]
            product_rows.append({
                "sku_id": sku,
                "sku_label": f"{row['description']} ({sku})",
                "description": row["description"],
                "category": row["category"],
            })
        return pd.DataFrame(product_rows).sort_values(["description", "sku_id"]).reset_index(drop=True)

    filters = get_portfolio_filters()
    filtered_sales, filtered_risk = apply_portfolio_filters(sales_daily, risk, filters)
    product_options = get_product_options(filtered_sales, filtered_risk, sku_master)

    if product_options.empty:
        st.warning("No SKUs match the current sidebar filters. Relax the filters to inspect product details.")
        st.stop()

    default_sku = st.session_state.get("product_details_sku")
    default_sku = str(default_sku) if default_sku is not None else None
    if default_sku not in [str(v) for v in product_options["sku_id"].tolist()]:
        default_sku = str(product_options.iloc[0]["sku_id"])

    option_labels = product_options["sku_label"].tolist()
    default_label = next((label for label in option_labels if str(label).endswith(f"({default_sku})")), option_labels[0])
    default_index = option_labels.index(default_label)
    selected_label = st.selectbox("Search / select a product", option_labels, index=default_index)
    sku_id = str(selected_label.split(" (")[-1].rstrip(")"))
    st.session_state["product_details_sku"] = sku_id

    meta = sku_master[sku_master["sku_id"] == sku_id].iloc[0]
    risk_row = risk[risk["sku_id"] == sku_id]
    if risk_row.empty:
        risk_row = filtered_risk[filtered_risk["sku_id"] == sku_id]
    risk_row = risk_row.iloc[0] if not risk_row.empty else None
    inv_row = latest_inv.loc[sku_id] if sku_id in latest_inv.index else None

    category_df = sku_master[sku_master["category"] == meta["category"]].copy()
    category_avg_price = category_df["list_price"].mean() if not category_df.empty else meta["list_price"]
    price_diff_pct = ((meta["list_price"] - category_avg_price) / category_avg_price * 100) if category_avg_price else 0.0
    avg_weekly_demand = weekly[weekly["sku_id"] == sku_id]["units_sold"].mean() if (weekly["sku_id"] == sku_id).any() else 0.0
    weeks_of_inventory = (inv_row["on_hand_units"] / avg_weekly_demand) if inv_row is not None and avg_weekly_demand > 0 else 0.0
    stockout_risk = float(risk_row["stockout_risk"]) if risk_row is not None else 0.0
    overstock_risk = float(risk_row["overstock_risk"]) if risk_row is not None else 0.0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        product_kpi_card("Category", meta["category"], f"Avg price: GBP {category_avg_price:,.2f}", f"Category average price: GBP {category_avg_price:,.2f}.")
    with c2:
        product_kpi_card("List price", f"GBP {meta['list_price']:.2f}", f"vs. category avg: {price_diff_pct:+.1f}%", f"Price difference vs. category average: {price_diff_pct:+.1f}%.")
    with c3:
        on_hand = inv_row["on_hand_units"] if inv_row is not None else 0
        product_kpi_card("On hand", f"{on_hand:,.0f}", f"Weeks of inventory: {weeks_of_inventory:.1f}", f"Average weekly demand: {avg_weekly_demand:,.1f} units; weeks of inventory: {weeks_of_inventory:.1f}.")
    with c4:
        q = risk_row["quadrant"] if risk_row is not None else "n/a"
        product_kpi_card("Risk quadrant", q, f"Stockout {stockout_risk:.1%} · Overstock {overstock_risk:.1%}", f"Stockout risk: {stockout_risk:.1%}; Overstock risk: {overstock_risk:.1%}.")

    overview_tab, sales_tab, inventory_tab, risk_tab, comparison_tab, insights_tab = st.tabs([
        "Overview",
        "Sales & Forecast",
        "Inventory",
        "Risk Analysis",
        "Comparison",
        "Insights",
    ])

    with overview_tab:
        st.markdown("### Product snapshot")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Description:** {meta['description']}")
            st.markdown(f"**SKU:** {meta['sku_id']}")
            st.markdown(f"**Category:** {meta['category']}")
            st.markdown(f"**List price:** GBP {meta['list_price']:.2f}")
        with col2:
            st.markdown(f"**Unit cost:** GBP {meta['unit_cost']:.2f}")
            st.markdown(f"**On hand:** {on_hand:,.0f}")
            st.markdown(f"**Reorder point:** {inv_row['reorder_point'] if inv_row is not None else 0:,.0f}")
            st.markdown(f"**Lead time:** {inv_row['lead_time_days'] if inv_row is not None else 0} days")

        if risk_row is not None:
            st.info(f"**Recommended action:** {risk_row['recommended_action']}")

    with sales_tab:
        sales_hist = sales_daily[sales_daily["sku_id"] == sku_id].copy()
        sales_hist = sales_hist.merge(calendar_df[["date", "is_holiday", "promo_event"]], on="date", how="left")
        sales_hist = sales_hist[(sales_hist["date"] >= pd.Timestamp(filters["date_range"][0])) & (sales_hist["date"] <= pd.Timestamp(filters["date_range"][1]))].sort_values("date")

        forecast_df = forecast[forecast["sku_id"] == sku_id].copy()
        forecast_df["week_start"] = pd.to_datetime(forecast_df["week_start"])

        st.markdown("#### Controls")
        legend_cols = st.columns(3)
        show_actual = legend_cols[0].checkbox("Actual", value=True, key=f"actual_toggle_{sku_id}")
        show_forecast = legend_cols[1].checkbox("Forecast", value=True, key=f"forecast_toggle_{sku_id}")
        metric_choice = legend_cols[2].selectbox("Metric", ["Units Sold", "Revenue", "Unit Price"], index=0)

        aggregation = st.radio("Aggregation", ["Daily", "Weekly", "Monthly"], horizontal=True)

        chart_start, chart_end = st.slider(
            "Date range",
            min_value=sales_hist["date"].min().date() if not sales_hist.empty else pd.Timestamp(filters["date_range"][0]).date(),
            max_value=sales_hist["date"].max().date() if not sales_hist.empty else pd.Timestamp(filters["date_range"][1]).date(),
            value=(pd.Timestamp(filters["date_range"][0]).date(), pd.Timestamp(filters["date_range"][1]).date()),
        )

        if not sales_hist.empty:
            hist_df = sales_hist[(sales_hist["date"] >= pd.Timestamp(chart_start)) & (sales_hist["date"] <= pd.Timestamp(chart_end))].copy()
            fig = go.Figure()
            if aggregation == "Daily":
                chart_data = hist_df[["date", "units_sold", "revenue", "unit_price", "promo_flag", "is_holiday", "promo_event"]].copy()
                metric_col = {"Units Sold": "units_sold", "Revenue": "revenue", "Unit Price": "unit_price"}[metric_choice]
                if show_actual:
                    fig.add_trace(go.Scatter(
                        x=chart_data["date"], y=chart_data[metric_col], mode="lines+markers", name="Actual",
                        line=dict(color=BRAND_PRIMARY, width=3), marker=dict(size=5),
                        customdata=chart_data[["date", "units_sold", "revenue", "unit_price", "promo_flag", "is_holiday", "promo_event"]].values,
                        hovertemplate="Date: %{customdata[0]|%Y-%m-%d}<br>Actual Units: %{customdata[1]:,.0f}<br>Forecast Units: N/A<br>Price: GBP %{customdata[3]:,.2f}<br>Promotion: %{customdata[4]}<br>Holiday: %{customdata[5]}<extra></extra>",
                    ))
                if show_forecast:
                    fig.add_trace(go.Scatter(
                        x=forecast_df["week_start"], y=forecast_df["pred"], mode="lines+markers", name="Forecast",
                        line=dict(color=BRAND_ACCENT, dash="dash", width=3), marker=dict(size=6),
                        hovertemplate="Date: %{x|%Y-%m-%d}<br>Forecast Units: %{y:,.0f}<br>Actual Units: N/A<br>Price: N/A<br>Promotion: N/A<br>Holiday: N/A<extra></extra>",
                    ))
            else:
                if aggregation == "Weekly":
                    chart_data = hist_df.copy(); chart_data["period"] = chart_data["date"] - pd.to_timedelta(chart_data["date"].dt.weekday, unit="D")
                else:
                    chart_data = hist_df.copy(); chart_data["period"] = chart_data["date"].dt.to_period("M").astype(str)
                chart_data = chart_data.groupby("period", as_index=False).agg(
                    units_sold=("units_sold", "sum"),
                    revenue=("revenue", "sum"),
                    unit_price=("unit_price", "mean"),
                    promo_flag=("promo_flag", "max"),
                    is_holiday=("is_holiday", "max"),
                )
                metric_col = {"Units Sold": "units_sold", "Revenue": "revenue", "Unit Price": "unit_price"}[metric_choice]
                if show_actual:
                    fig.add_trace(go.Scatter(
                        x=chart_data["period"], y=chart_data[metric_col], mode="lines+markers", name="Actual",
                        line=dict(color=BRAND_PRIMARY, width=3), marker=dict(size=6),
                        customdata=chart_data[["period", "units_sold", "revenue", "unit_price", "promo_flag", "is_holiday"]].values,
                        hovertemplate="Date: %{customdata[0]}<br>Actual Units: %{customdata[1]:,.0f}<br>Forecast Units: N/A<br>Price: GBP %{customdata[3]:,.2f}<br>Promotion: %{customdata[4]}<br>Holiday: %{customdata[5]}<extra></extra>",
                    ))
                if show_forecast:
                    forecast_period = forecast_df[["week_start", "pred"]].rename(columns={"week_start": "period"})
                    fig.add_trace(go.Scatter(
                        x=forecast_period["period"], y=forecast_period["pred"], mode="lines+markers", name="Forecast",
                        line=dict(color=BRAND_ACCENT, dash="dash", width=3), marker=dict(size=6),
                        hovertemplate="Date: %{x|%Y-%m-%d}<br>Forecast Units: %{y:,.0f}<br>Actual Units: N/A<br>Price: N/A<br>Promotion: N/A<br>Holiday: N/A<extra></extra>",
                    ))

            fig.update_layout(
                template=PLOTLY_TEMPLATE,
                height=470,
                xaxis_title="Date",
                yaxis_title={"Units Sold": "Units", "Revenue": "GBP", "Unit Price": "GBP"}[metric_choice],
                legend=dict(orientation="h", y=1.12),
                margin=dict(l=10, r=10, t=20, b=10),
            )
            fig.update_xaxes(rangeslider_visible=True, type="date")
            fig.update_layout(hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True, "responsive": True})
            chart_html = fig.to_html(include_plotlyjs="cdn")
            st.download_button("Download chart", data=chart_html, file_name=f"product_{sku_id}_sales_forecast.html", mime="text/html")
        else:
            st.info("No sales history is available for the selected date range.")

    with inventory_tab:
        section("Inventory coverage")
        if inv_row is not None:
            on_hand = float(inv_row["on_hand_units"])
            on_order = float(inv_row["on_order_units"])
            lead_time_days = float(inv_row["lead_time_days"])
            reorder_point = float(inv_row["reorder_point"])
            avg_demand_day = avg_weekly_demand / 7
            lead_time_demand = avg_demand_day * lead_time_days
            coverage = (on_hand + on_order) / max(avg_weekly_demand, 1)
            inv_cols = st.columns(4)
            inv_cols[0].metric("On hand", f"{on_hand:,.0f}")
            inv_cols[1].metric("On order", f"{on_order:,.0f}")
            inv_cols[2].metric("Reorder point", f"{reorder_point:,.0f}")
            inv_cols[3].metric("Weeks cover", f"{coverage:.1f}")
            st.caption(f"Average weekly demand: {avg_weekly_demand:,.1f} units | Lead-time demand: {lead_time_demand:,.1f} units | Lead time: {lead_time_days} days")
        else:
            st.info("Inventory snapshot is not available for this SKU.")

    with risk_tab:
        if risk_row is not None:
            so = float(risk_row["stockout_risk"])
            ov = float(risk_row["overstock_risk"])
            current_inventory = float(inv_row["on_hand_units"]) if inv_row is not None else 0.0
            lead_time_demand = float(risk_row["forecast_demand_leadtime"]) if "forecast_demand_leadtime" in risk_row.index else 0.0
            recommendation = risk_row["recommended_action"]
            risk_level = "High" if so >= 0.5 else "Moderate" if so > 0.2 else "Low"

            c1, c2 = st.columns(2)
            for idx, (label, value, color) in enumerate([
                ("Stockout Risk", so * 100, "#D9534F"),
                ("Overstock Risk", ov * 100, "#5B5FC7"),
            ]):
                with c1 if idx == 0 else c2:
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=value,
                        title={"text": label},
                        number={"suffix": "%"},
                        domain={"x": [0, 1], "y": [0, 1]},
                        gauge={
                           "axis": {"range": [0, 100], "tickwidth": 1},
                           "bar": {"color": color},
                           "bgcolor": "white",
                           "steps": [
                               {"range": [0, 50], "color": "#F4F4FB"},
                               {"range": [50, 100], "color": "#E8E4FF"},
                           ],
                        },
                    ))
                    fig.update_layout(height=260, margin=dict(l=15, r=15, t=30, b=10))
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True, "scrollZoom": True})
                    st.caption(
                        f"Current inventory: {current_inventory:,.0f} units | "
                        f"Average weekly demand: {avg_weekly_demand:,.1f} | "
                        f"Lead-time demand: {lead_time_demand:,.1f} | "
                        f"Risk level: {risk_level} | "
                        f"Recommended action: {recommendation}"
                    )

            st.markdown("**Risk details**")
            st.write(f"- Current inventory: {current_inventory:,.0f} units")
            st.write(f"- Average weekly demand: {avg_weekly_demand:,.1f} units")
            st.write(f"- Lead-time demand: {lead_time_demand:,.1f} units")
            st.write(f"- Risk level: {risk_level}")
            st.write(f"- Recommended action: {recommendation}")
        else:
            st.info("No risk score is available for this SKU.")

    with comparison_tab:
        available_compare_skus = [sku for sku in product_options["sku_id"].tolist() if sku != sku_id]
        if not available_compare_skus:
            st.info("No second SKU is available in the current filter set to compare against.")
        else:
            compare_sku = st.selectbox("Compare with SKU", available_compare_skus, index=0)
            compare_meta = sku_master[sku_master["sku_id"] == compare_sku].iloc[0]
            compare_risk = risk[risk["sku_id"] == compare_sku].iloc[0] if not risk[risk["sku_id"] == compare_sku].empty else None
            compare_inv = latest_inv.loc[compare_sku] if compare_sku in latest_inv.index else None

            metric_rows = [
                ("Price", meta["list_price"], compare_meta["list_price"]),
                ("Units Sold", sales_daily[sales_daily["sku_id"] == sku_id]["units_sold"].sum(), sales_daily[sales_daily["sku_id"] == compare_sku]["units_sold"].sum()),
                ("Revenue", sales_daily[sales_daily["sku_id"] == sku_id]["revenue"].sum(), sales_daily[sales_daily["sku_id"] == compare_sku]["revenue"].sum()),
                ("Demand", weekly[weekly["sku_id"] == sku_id]["units_sold"].sum(), weekly[weekly["sku_id"] == compare_sku]["units_sold"].sum()),
                ("Inventory", (inv_row["on_hand_units"] if inv_row is not None else 0), (compare_inv["on_hand_units"] if compare_inv is not None else 0)),
                ("Risk", float(risk_row["stockout_risk"]) if risk_row is not None else 0.0, float(compare_risk["stockout_risk"]) if compare_risk is not None else 0.0),
            ]
            comparison_df = pd.DataFrame(metric_rows, columns=["Metric", "Selected SKU", "Compared SKU"])
            st.dataframe(comparison_df, use_container_width=True, hide_index=True)

            fig = px.bar(
                comparison_df.melt(id_vars="Metric", value_vars=["Selected SKU", "Compared SKU"], var_name="SKU", value_name="Value"),
                x="Metric",
                y="Value",
                color="SKU",
                barmode="group",
                template=PLOTLY_TEMPLATE,
                color_discrete_map={"Selected SKU": BRAND_PRIMARY, "Compared SKU": BRAND_ACCENT},
            )
            fig.update_layout(height=360, xaxis_title="", yaxis_title="Value", legend_title="")
            st.plotly_chart(fig, use_container_width=True)

    with insights_tab:
        insights = []
        if avg_weekly_demand > 0:
            insights.append(f"Average weekly demand is {avg_weekly_demand:,.1f} units, giving {weeks_of_inventory:.1f} weeks of inventory cover.")
        if category_avg_price:
            insights.append(f"List price is {price_diff_pct:+.1f}% vs. the category average of GBP {category_avg_price:,.2f}.")
        if risk_row is not None:
            insights.append(f"This SKU is currently classified as {risk_row['quadrant']} with stockout risk at {stockout_risk:.1%} and overstock risk at {overstock_risk:.1%}.")
            insights.append(f"Recommendation: {risk_row['recommended_action']}")
        if inv_row is not None and avg_weekly_demand > 0:
            insights.append(f"Current stock of {inv_row['on_hand_units']:,.0f} units is {((inv_row['on_hand_units'] / max(avg_weekly_demand, 1)) - 1) * 100:+.1f}% versus the weekly demand run-rate.")
        insights = insights[:5]
        for insight in insights:
            st.markdown(f"- {insight}")

        if not insights:
            st.info("Not enough data available to generate product insights for this SKU.")

    st.markdown("---")


# ========================================================================================
# PAGE: EXECUTIVE SUMMARY
# ========================================================================================
elif page == "📊 Executive Summary":
    st.markdown("# Executive Summary")
    st.caption("For the Head of Operations & Finance — chart types: bar, sunburst, donut")

    total_at_risk = risk["sales_at_risk_rupees"].sum()
    total_locked = risk["capital_locked_rupees"].sum()
    c1, c2, c3, c4 = st.columns(4)
    with c1: kpi_card("Forecast improvement vs. guessing", f"{100*(metrics['avg_baseline_wape']-metrics['avg_lgbm_wape'])/metrics['avg_baseline_wape']:.0f}%", "vs. seasonal-naive baseline")
    with c2: kpi_card("Sales at risk (stockout)", money(total_at_risk))
    with c3: kpi_card("Capital locked (overstock)", money(total_locked))
    with c4: kpi_card("Total rupee opportunity", money(total_at_risk + total_locked))

    st.markdown("### What this means for NorthBay")
    st.markdown(f"""
    - **{int((risk['quadrant']=='Reorder Now').sum())} SKUs** need a replenishment order raised now to avoid a stockout.
    - **{int((risk['quadrant']=='Markdown / Clear').sum())} SKUs** are overstocked and are good markdown/clearance candidates to free up cash.
    - The demand forecast beats a simple "same as last year" guess by
      **{100*(metrics['avg_baseline_wape']-metrics['avg_lgbm_wape'])/metrics['avg_baseline_wape']:.0f}%** on a 3-fold backtest — directionally reliable, not
      precise to the unit, so best used to prioritise attention rather than set exact order sizes.
    """)

    c1, c2 = st.columns(2)
    with c1:
        section("Revenue concentration")
        tm = sales_daily.groupby(["category", "sku_id", "description"])["revenue"].sum().reset_index()
        fig = px.sunburst(tm, path=["category", "description"], values="revenue",
                           color="revenue", color_continuous_scale="Purples", template=PLOTLY_TEMPLATE)
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        section("Where the risk sits, by category")
        cat_risk = risk.groupby("category")[["sales_at_risk_rupees", "capital_locked_rupees"]].sum().reset_index()
        cat_risk = cat_risk.sort_values("sales_at_risk_rupees", ascending=False).head(10)
        fig = px.bar(cat_risk, x="category", y=["sales_at_risk_rupees", "capital_locked_rupees"],
                     barmode="group", template=PLOTLY_TEMPLATE,
                     color_discrete_sequence=["#D9534F", "#5B5FC7"])
        fig.update_xaxes(tickangle=45)
        fig.update_layout(height=420, legend_title="", yaxis_title="GBP")
        st.plotly_chart(fig, use_container_width=True)

    section("Top 10 SKUs by rupee value at stake")
    top10 = risk.sort_values("revenue_at_stake", ascending=False).head(10)
    st.dataframe(
        top10[["sku_id", "description", "category", "quadrant", "revenue_at_stake", "recommended_action"]],
        use_container_width=True,
        column_config={"revenue_at_stake": st.column_config.NumberColumn("Value at stake", format="GBP %.0f")},
    )

    st.markdown("---")
    st.caption(
        "Limitations to keep in mind: unit cost and inventory position are simulated (no real "
        "feed was provided); category labels are keyword-derived, not a real merchandising "
        "taxonomy. Both should be replaced/reviewed before this drives live purchasing decisions."
    )


# ========================================================================================
# PAGE: WHAT-IF SIMULATOR  (extra feature #1 — beyond the brief's required scope)
# ========================================================================================
elif page == "🎛️ What-If Simulator":
    st.markdown("# What-If Simulator")
    st.caption(
        "Extra feature — adjust a SKU's lead time, safety stock, and expected demand growth "
        "and watch its risk score recalculate live. Chart type: gauge/indicator."
    )

    sku_options = sku_master.sort_values("description")["sku_id"] + " — " + sku_master.sort_values("description")["description"]
    sku_lookup = dict(zip(sku_options, sku_master.sort_values("description")["sku_id"]))
    choice = st.selectbox("Choose a SKU to simulate", list(sku_lookup.keys()), key="whatif_sku")
    sku_id = sku_lookup[choice]

    base_row = risk[risk["sku_id"] == sku_id]
    if base_row.empty or sku_id not in latest_inv.index:
        st.warning("No risk/inventory data available for this SKU.")
    else:
        base_row = base_row.iloc[0]
        inv_row = latest_inv.loc[sku_id]
        meta = sku_master[sku_master["sku_id"] == sku_id].iloc[0]

        c1, c2, c3 = st.columns(3)
        with c1:
            lead_time = st.slider("Lead time (days)", 1, 30, int(inv_row["lead_time_days"]))
        with c2:
            demand_growth = st.slider("Expected demand change (%)", -50, 100, 0, step=5)
        with c3:
            extra_stock = st.slider("Extra safety stock (units)", -200, 500, 0, step=10)

        adj_daily_rate = base_row["forecast_daily_rate"] * (1 + demand_growth / 100)
        forecast_leadtime = adj_daily_rate * lead_time
        forecast_horizon = adj_daily_rate * metrics["horizon_weeks"] * 7
        on_hand = inv_row["on_hand_units"] + extra_stock
        on_order = inv_row["on_order_units"]

        shortfall = max(forecast_leadtime - (on_hand + on_order), 0)
        stockout_risk = min(shortfall / forecast_leadtime, 1) if forecast_leadtime > 0 else 0
        excess = max(on_hand - forecast_horizon, 0)
        overstock_risk = min(excess / on_hand, 1) if on_hand > 0 else 0
        sales_at_risk = shortfall * meta["list_price"]
        capital_locked = excess * meta["unit_cost"]

        if stockout_risk >= 0.5 and overstock_risk >= 0.5:
            quadrant = "Watch / Volatile"
        elif stockout_risk >= 0.5:
            quadrant = "Reorder Now"
        elif overstock_risk >= 0.5:
            quadrant = "Markdown / Clear"
        else:
            quadrant = "Healthy"

        st.markdown("### Simulated result")
        c1, c2 = st.columns(2)
        with c1:
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta", value=stockout_risk * 100,
                delta={"reference": base_row["stockout_risk"] * 100},
                title={"text": "Stockout risk (simulated)"}, number={"suffix": "%"},
                gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#D9534F"}}))
            fig.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig2 = go.Figure(go.Indicator(
                mode="gauge+number+delta", value=overstock_risk * 100,
                delta={"reference": base_row["overstock_risk"] * 100},
                title={"text": "Overstock risk (simulated)"}, number={"suffix": "%"},
                gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#5B5FC7"}}))
            fig2.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=10))
            st.plotly_chart(fig2, use_container_width=True)

        color = COLOR_MAP.get(quadrant, "#999")
        st.markdown(f"""
        <div class="alert-card" style="border-left-color:{color};">
            <span class="badge" style="background:{color};">{quadrant}</span>
            Simulated sales-at-risk: <b>{money(sales_at_risk)}</b> &nbsp;|&nbsp;
            Simulated capital locked: <b>{money(capital_locked)}</b>
            <br><span class="kpi-sub">Baseline (current data) was: {base_row['quadrant']} —
            {money(base_row['sales_at_risk_rupees'])} at risk, {money(base_row['capital_locked_rupees'])} locked</span>
        </div>
        """, unsafe_allow_html=True)
        st.caption(
            "This uses the same stockout/overstock formulas as the production risk model, just "
            "recomputed instantly with your adjusted assumptions — useful for testing 'what if "
            "we shortened the lead time' or 'what if demand grows 20%' before committing to a "
            "real reorder."
        )


# ========================================================================================
# PAGE: ALERTS CENTER  (extra feature #2 — beyond the brief's required scope)
# ========================================================================================
elif page == "🔔 Alerts Center":
    filters = get_portfolio_filters()
    _, filtered_risk = apply_portfolio_filters(sales_daily, risk, filters)

    st.markdown("# Alerts Center")
    st.caption(
        "Extra feature — an auto-generated, prioritised feed of the situations that need "
        "attention today, the way a real ops tool would surface them. Chart type: funnel + bar."
    )

    severity_order = {"Reorder Now": 0, "Watch / Volatile": 1, "Markdown / Clear": 2}
    alerts = filtered_risk[filtered_risk["quadrant"] != "Healthy"].copy()
    alerts["severity_rank"] = alerts["quadrant"].map(severity_order)
    alerts = alerts.sort_values(["severity_rank", "revenue_at_stake"], ascending=[True, False])

    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("🔴 Critical (Reorder Now)", int((alerts['quadrant'] == 'Reorder Now').sum()))
    with c2: kpi_card("🟠 Watch / Volatile", int((alerts['quadrant'] == 'Watch / Volatile').sum()))
    with c3: kpi_card("🔵 Markdown / Clear", int((alerts['quadrant'] == 'Markdown / Clear').sum()))

    sev_filter = st.multiselect("Filter by severity", alerts["quadrant"].unique().tolist(), default=[])
    show_alerts = alerts if not sev_filter else alerts[alerts["quadrant"].isin(sev_filter)]

    section(f"{len(show_alerts)} active alerts")
    icon_map = {"Reorder Now": "🔴", "Watch / Volatile": "🟠", "Markdown / Clear": "🔵"}
    for _, r in show_alerts.head(25).iterrows():
        color = COLOR_MAP.get(r["quadrant"], "#999")
        icon = icon_map.get(r["quadrant"], "⚪")
        if r["quadrant"] == "Reorder Now":
            detail = f"Projected to run short by lead-time end — {money(r['sales_at_risk_rupees'])} in sales at risk."
        elif r["quadrant"] == "Markdown / Clear":
            detail = f"Holding far more stock than forecast demand — {money(r['capital_locked_rupees'])} of capital locked."
        else:
            detail = "High risk on both stockout and overstock — demand looks erratic, review manually."
        st.markdown(f"""
        <div class="alert-card" style="border-left-color:{color};">
            {icon} <span class="badge" style="background:{color};">{r['quadrant']}</span>
            <b>{r['description']}</b> ({r['sku_id']}, {r['category']})
            <br>{detail}
            <br><span class="kpi-sub">Recommended: {r['recommended_action']}</span>
        </div>
        """, unsafe_allow_html=True)

    st.download_button("⬇ Download all alerts (CSV)", alerts.to_csv(index=False).encode(),
                        "foresight_alerts.csv", "text/csv")
