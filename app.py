from __future__ import annotations

from contextlib import contextmanager
from io import StringIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data.mock_data import get_default_positions, get_fund_snapshots, get_mock_trend, search_fund
from utils.analysis import calc_portfolio_kpis, calc_position_metrics, generate_auto_insights

st.set_page_config(page_title="Fund Valuation Dashboard", page_icon="📊", layout="wide")

I18N = {
    "zh": {
        "app_title": "基金估值与持仓收益分析 Dashboard",
        "app_subtitle": "面向作品集展示的基金分析 MVP（支持后续接入真实数据源）",
        "lang_label": "语言",
        "theme_tip": "提示：使用右上角系统主题切换可体验 Light / Dark 模式。",
        "hero_title": "一站式基金估值、收益与风险洞察",
        "hero_desc": "输入基金与持仓信息，自动生成估值、收益和组合分析结论。",
        "hero_bullets": ["基金查询", "持仓收益测算", "图表分析", "自动洞察"],
        "empty_title": "欢迎使用基金 Dashboard",
        "empty_desc": "你可以先直接体验默认示例持仓，或在下方自行输入你的基金持仓。",
        "guide_steps": [
            "1) 在“基金查询”输入代码/名称，查看净值与估值。",
            "2) 在“我的持仓”编辑份额和成本。",
            "3) 在 KPI 和图表区域查看收益表现。",
            "4) 阅读“自动分析结论”作为每日复盘参考。",
        ],
        "query_header": "基金查询",
        "query_input": "输入基金代码或基金名称",
        "query_table": "基金估值结果",
        "holdings_header": "我的持仓",
        "use_default": "加载示例持仓",
        "fallback_editor_hint": "当前 Streamlit 版本不支持交互表格，已切换为 CSV 文本编辑模式（列：code,name,shares,cost_per_share）。",
        "kpi_header": "KPI 核心指标",
        "kpi_total_cost": "总持仓成本",
        "kpi_market": "当前持仓市值",
        "kpi_today_profit": "今日预估总收益",
        "kpi_return": "组合累计收益率",
        "analysis_header": "持仓收益分析",
        "charts_header": "图表区",
        "chart_nav": "基金净值 / 估值趋势",
        "chart_profit": "持仓今日预估收益分布",
        "insights_header": "自动分析结论",
    },
    "en": {
        "app_title": "Fund Valuation & Portfolio Analytics Dashboard",
        "app_subtitle": "Portfolio-ready MVP with clean architecture and easy future API integration",
        "lang_label": "Language",
        "theme_tip": "Tip: switch between Light / Dark themes via Streamlit settings.",
        "hero_title": "One-stop valuation, performance, and risk insight",
        "hero_desc": "Input funds and positions to get instant valuation, PnL, and portfolio-level conclusions.",
        "hero_bullets": ["Fund lookup", "PnL calculator", "Interactive charts", "Auto insights"],
        "empty_title": "Welcome to the Fund Dashboard",
        "empty_desc": "Try the built-in sample portfolio first, or enter your own holdings below.",
        "guide_steps": [
            "1) Search by code/name in Fund Lookup.",
            "2) Edit shares and costs in My Holdings.",
            "3) Review KPIs and charted performance.",
            "4) Use Auto Insights for quick daily recap.",
        ],
        "query_header": "Fund Lookup",
        "query_input": "Search by fund code or name",
        "query_table": "Fund valuation results",
        "holdings_header": "My Holdings",
        "use_default": "Load sample holdings",
        "fallback_editor_hint": "Your Streamlit version does not support editable tables. Falling back to CSV text editing (columns: code,name,shares,cost_per_share).",
        "kpi_header": "KPI Overview",
        "kpi_total_cost": "Total Cost",
        "kpi_market": "Current Market Value",
        "kpi_today_profit": "Today's Estimated PnL",
        "kpi_return": "Portfolio Return Rate",
        "analysis_header": "Holdings PnL Analysis",
        "charts_header": "Charts",
        "chart_nav": "Fund NAV vs Estimated NAV Trend",
        "chart_profit": "Today's estimated PnL by position",
        "insights_header": "Automated Insights",
    },
}


@contextmanager
def compat_container(border: bool = False):
    """Graceful fallback for old Streamlit versions without border argument."""
    try:
        with st.container(border=border):
            yield
    except TypeError:
        with st.container():
            yield
            if border:
                st.markdown("---")


def safe_dataframe(df: pd.DataFrame):
    try:
        st.dataframe(df, use_container_width=True)
    except TypeError:
        st.dataframe(df)


def safe_plotly_chart(fig):
    try:
        st.plotly_chart(fig, use_container_width=True)
    except TypeError:
        st.plotly_chart(fig)


def render_positions_editor(positions: pd.DataFrame, hint_text: str) -> pd.DataFrame:
    if hasattr(st, "data_editor"):
        kwargs = {
            "num_rows": "dynamic",
            "key": "positions_editor",
        }
        if hasattr(st, "column_config"):
            kwargs["column_config"] = {
                "code": st.column_config.TextColumn("Code"),
                "name": st.column_config.TextColumn("Name"),
                "shares": st.column_config.NumberColumn("Shares", min_value=0.0, step=100.0),
                "cost_per_share": st.column_config.NumberColumn("Cost/Share", min_value=0.0, step=0.01),
            }
        try:
            return st.data_editor(positions, use_container_width=True, **kwargs)
        except TypeError:
            return st.data_editor(positions, **kwargs)

    if hasattr(st, "experimental_data_editor"):
        try:
            return st.experimental_data_editor(positions, num_rows="dynamic", key="positions_editor")
        except TypeError:
            return st.experimental_data_editor(positions, key="positions_editor")

    st.info(hint_text)
    csv_text = st.text_area(
        "CSV",
        value=positions.to_csv(index=False),
        height=180,
        key="positions_csv_editor",
    )
    try:
        parsed = pd.read_csv(StringIO(csv_text))
    except Exception:
        st.warning("CSV parse failed. Reverting to previous holdings.")
        return positions

    required_cols = ["code", "name", "shares", "cost_per_share"]
    for col in required_cols:
        if col not in parsed.columns:
            parsed[col] = "" if col in {"code", "name"} else 0.0
    return parsed[required_cols]


def money(x: float) -> str:
    return f"¥{x:,.2f}"


def pct(x: float) -> str:
    return f"{x * 100:.2f}%"


col_lang, col_tip = st.columns([1, 3])
with col_lang:
    language = st.selectbox(
        I18N["zh"]["lang_label"],
        ["zh", "en"],
        format_func=lambda x: "中文" if x == "zh" else "English",
    )
L = I18N[language]
with col_tip:
    st.info(L["theme_tip"])

st.title(L["app_title"])
st.caption(L["app_subtitle"])

with compat_container(border=True):
    st.subheader(L["hero_title"])
    st.write(L["hero_desc"])
    bullet_cols = st.columns(len(L["hero_bullets"]))
    for i, b in enumerate(L["hero_bullets"]):
        bullet_cols[i].success(f"✓ {b}")

with compat_container(border=True):
    st.subheader(L["empty_title"])
    st.write(L["empty_desc"])
    for step in L["guide_steps"]:
        st.write(step)

fund_snapshot = get_fund_snapshots()

st.header(L["query_header"])
query = st.text_input(L["query_input"], placeholder="161725 / 白酒 / consumer")
fund_results = search_fund(query)

show_cols = ["code", "name_zh", "name_en", "nav", "est_nav", "day_change_pct"]
safe_dataframe(
    fund_results[show_cols].rename(
        columns={
            "code": "Code",
            "name_zh": "Name(ZH)",
            "name_en": "Name(EN)",
            "nav": "NAV",
            "est_nav": "Est NAV",
            "day_change_pct": "Day %",
        }
    )
)

st.header(L["holdings_header"])
if "positions" not in st.session_state:
    st.session_state.positions = get_default_positions()

if st.button(L["use_default"]):
    st.session_state.positions = get_default_positions()

edited_positions = render_positions_editor(st.session_state.positions, L["fallback_editor_hint"])
st.session_state.positions = edited_positions

positions_clean = edited_positions.dropna(subset=["code", "shares", "cost_per_share"]).copy()
positions_clean["code"] = positions_clean["code"].astype(str)

position_metrics = calc_position_metrics(positions_clean, fund_snapshot)
kpis = calc_portfolio_kpis(position_metrics)

st.header(L["kpi_header"])
k1, k2, k3, k4 = st.columns(4)
k1.metric(L["kpi_total_cost"], money(kpis["total_cost"]))
k2.metric(L["kpi_market"], money(kpis["total_market"]))
k3.metric(L["kpi_today_profit"], money(kpis["today_est_profit"]))
k4.metric(L["kpi_return"], pct(kpis["total_return_rate"]))

st.header(L["analysis_header"])
analysis_cols = [
    "code",
    "name",
    "shares",
    "cost_per_share",
    "nav",
    "est_nav",
    "day_change_pct",
    "today_est_profit",
    "total_profit",
    "profit_rate",
]
safe_dataframe(
    position_metrics[analysis_cols].rename(
        columns={
            "code": "Code",
            "name": "Name",
            "shares": "Shares",
            "cost_per_share": "Cost/Share",
            "nav": "NAV",
            "est_nav": "Est NAV",
            "day_change_pct": "Day %",
            "today_est_profit": "Today Est PnL",
            "total_profit": "Total PnL",
            "profit_rate": "Return Rate",
        }
    )
)

st.header(L["charts_header"])
left, right = st.columns(2)

with left:
    st.subheader(L["chart_nav"])
    chart_fund_code = st.selectbox("Chart Fund", fund_snapshot["code"].tolist(), index=0)
    trend_df = get_mock_trend(chart_fund_code, days=90)
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(x=trend_df["date"], y=trend_df["nav"], mode="lines", name="NAV"))
    fig_trend.add_trace(go.Scatter(x=trend_df["date"], y=trend_df["est_nav"], mode="lines", name="Est NAV"))
    fig_trend.update_layout(height=360, margin=dict(l=20, r=20, t=20, b=20), legend=dict(orientation="h"))
    fig_trend.update_xaxes(nticks=8)
    safe_plotly_chart(fig_trend)

with right:
    st.subheader(L["chart_profit"])
    if position_metrics.empty:
        st.warning("No holdings yet." if language == "en" else "暂无持仓数据。")
    else:
        fig_bar = px.bar(
            position_metrics,
            x="name",
            y="today_est_profit",
            color="today_est_profit",
            color_continuous_scale="RdYlGn",
        )
        fig_bar.update_layout(height=360, margin=dict(l=20, r=20, t=20, b=20), xaxis_title=None, yaxis_title=None)
        safe_plotly_chart(fig_bar)

st.header(L["insights_header"])
for insight in generate_auto_insights(position_metrics, language=language):
    st.write(f"- {insight}")

st.caption("MVP note: this version uses deterministic mock data for valuation/trend and can be swapped to real fund APIs later.")
