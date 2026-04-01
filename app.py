from __future__ import annotations

from contextlib import contextmanager

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data.providers.registry import get_fund_data_provider
from utils.analysis import calc_portfolio_kpis, calc_position_metrics, generate_auto_insights

st.set_page_config(page_title="Fund Valuation Dashboard", page_icon="📊", layout="wide")

I18N = {
    "zh": {
        "app_title": "基金估值与持仓收益分析 Dashboard",
        "app_subtitle": "面向作品集展示的双栏基金分析 Dashboard（支持后续接入真实数据源）",
        "lang_label": "语言",
        "theme_tip": "提示：使用右上角系统主题切换可体验 Light / Dark 模式。",
        "hero_title": "正式版基金分析工作台",
        "hero_desc": "支持基金检索、持仓增删改、KPI 与趋势图联动，数据层已抽象为可替换 Provider。",
        "hero_bullets": ["可扩展基金库", "可编辑持仓", "中英双语图表", "自动分析"],
        "query_header": "基金查询与筛选",
        "query_input": "输入基金代码、名称或分类",
        "query_table": "基金估值结果",
        "holdings_header": "我的持仓（可编辑）",
        "add_position": "新增基金到持仓",
        "clear_positions": "清空全部持仓",
        "use_default": "一键加载示例持仓",
        "edit_tip": "可直接在下方表格编辑代码、名称、份额与成本。",
        "kpi_header": "KPI 核心指标",
        "kpi_total_cost": "总持仓成本",
        "kpi_market": "当前持仓市值",
        "kpi_today_profit": "今日预估总收益",
        "kpi_return": "组合累计收益率",
        "analysis_header": "持仓收益分析",
        "charts_header": "图表区",
        "chart_nav": "基金净值 / 估值趋势",
        "chart_profit": "持仓今日预估收益分布",
        "chart_fund": "图表基金",
        "insights_header": "自动分析结论",
        "source_header": "数据来源说明",
        "source_label": "数据来源",
        "source_mode": "数据模式",
        "source_time": "更新时间(UTC)",
        "mock_flag": "当前为示例/估算数据，非真实交易参考。",
        "provider_load_failed": "数据源加载失败，已回退到本地 mock 数据。原因：",
        "empty_holdings": "暂无持仓数据。",
        "delete_help": "在表格中删除行即可删除单只基金。",
        "left_panel": "左侧：查询与持仓操作",
        "right_panel": "右侧：KPI / 图表 / 结论",
    },
    "en": {
        "app_title": "Fund Valuation & Portfolio Analytics Dashboard",
        "app_subtitle": "Portfolio-ready two-column dashboard with replaceable data provider architecture",
        "lang_label": "Language",
        "theme_tip": "Tip: switch between Light / Dark themes via Streamlit settings.",
        "hero_title": "Production-style fund analytics workspace",
        "hero_desc": "Fund lookup, editable holdings, KPI and chart linkage, with pluggable provider-based data layer.",
        "hero_bullets": ["Extensible catalog", "Editable holdings", "Bilingual chart labels", "Auto insights"],
        "query_header": "Fund Lookup & Filter",
        "query_input": "Search by code, name, or category",
        "query_table": "Fund valuation results",
        "holdings_header": "My Holdings (Editable)",
        "add_position": "Add fund to holdings",
        "clear_positions": "Clear all holdings",
        "use_default": "Load sample holdings",
        "edit_tip": "Edit code, name, shares, and cost directly in the table below.",
        "kpi_header": "KPI Overview",
        "kpi_total_cost": "Total Cost",
        "kpi_market": "Current Market Value",
        "kpi_today_profit": "Today's Estimated PnL",
        "kpi_return": "Portfolio Return Rate",
        "analysis_header": "Holdings PnL Analysis",
        "charts_header": "Charts",
        "chart_nav": "Fund NAV vs Estimated NAV Trend",
        "chart_profit": "Today's estimated PnL by position",
        "chart_fund": "Chart fund",
        "insights_header": "Automated Insights",
        "source_header": "Data Source",
        "source_label": "Source",
        "source_mode": "Mode",
        "source_time": "Updated at (UTC)",
        "mock_flag": "Current values are sample/estimated data and not trading advice.",
        "provider_load_failed": "Provider load failed. Fallback to local mock data. Reason:",
        "empty_holdings": "No holdings yet.",
        "delete_help": "Delete a single fund by removing a row from the editable table.",
        "left_panel": "Left: lookup & holdings operations",
        "right_panel": "Right: KPI / charts / insights",
    },
}


@contextmanager
def compat_container(border: bool = False):
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


def money(x: float) -> str:
    return f"¥{x:,.2f}"


def pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def ensure_position_schema(df: pd.DataFrame) -> pd.DataFrame:
    wanted = ["code", "name", "shares", "cost_per_share"]
    data = df.copy()
    for c in wanted:
        if c not in data.columns:
            data[c] = "" if c in {"code", "name"} else 0.0
    data = data[wanted]
    data["code"] = data["code"].astype(str)
    data["name"] = data["name"].astype(str)
    data["shares"] = pd.to_numeric(data["shares"], errors="coerce").fillna(0.0)
    data["cost_per_share"] = pd.to_numeric(data["cost_per_share"], errors="coerce").fillna(0.0)
    return data


def render_positions_editor(positions: pd.DataFrame, language: str) -> pd.DataFrame:
    if not hasattr(st, "data_editor"):
        st.warning("Please upgrade Streamlit for editable holdings table." if language == "en" else "请升级 Streamlit 版本以使用可编辑表格。")
        return positions

    label_map = {
        "code": "Code" if language == "en" else "基金代码",
        "name": "Name" if language == "en" else "基金名称",
        "shares": "Shares" if language == "en" else "持仓份额",
        "cost_per_share": "Cost/Share" if language == "en" else "持仓成本",
    }

    kwargs = {"num_rows": "dynamic", "key": "positions_editor"}
    if hasattr(st, "column_config"):
        kwargs["column_config"] = {
            "code": st.column_config.TextColumn(label_map["code"]),
            "name": st.column_config.TextColumn(label_map["name"]),
            "shares": st.column_config.NumberColumn(label_map["shares"], min_value=0.0, step=100.0),
            "cost_per_share": st.column_config.NumberColumn(label_map["cost_per_share"], min_value=0.0, step=0.01),
        }
    edited = st.data_editor(positions, **kwargs)
    return ensure_position_schema(edited)


provider = get_fund_data_provider()
plotly_template = "plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white"

col_lang, col_tip = st.columns([1, 3])
with col_lang:
    language = st.selectbox(I18N["zh"]["lang_label"], ["zh", "en"], format_func=lambda x: "中文" if x == "zh" else "English")
L = I18N[language]
with col_tip:
    st.info(L["theme_tip"])

st.title(L["app_title"])
st.caption(L["app_subtitle"])

with compat_container(border=True):
    st.subheader(L["hero_title"])
    st.write(L["hero_desc"])
    cols = st.columns(len(L["hero_bullets"]))
    for i, item in enumerate(L["hero_bullets"]):
        cols[i].success(f"✓ {item}")

try:
    fund_snapshot = provider.get_snapshots()
except Exception as exc:  # noqa: BLE001
    from data.providers.mock_provider import LocalMockFundProvider

    st.error(f"{L['provider_load_failed']} {exc}")
    provider = LocalMockFundProvider()
    fund_snapshot = provider.get_snapshots()
if "positions" not in st.session_state:
    st.session_state.positions = provider.get_default_positions()

left_col, right_col = st.columns([1.12, 1.35], gap="large")

with left_col:
    with compat_container(border=True):
        st.caption(L["left_panel"])
        st.subheader(L["query_header"])
        query = st.text_input(L["query_input"], placeholder="161725 / 白酒 / consumer")
        try:
            fund_results = provider.search(query)
        except Exception as exc:  # noqa: BLE001
            st.error(f"{L['provider_load_failed']} {exc}")
            fund_results = fund_snapshot
        show_cols = ["code", "name_zh", "name_en", "category", "nav", "est_nav", "day_change_pct"]
        safe_dataframe(
            fund_results[show_cols].rename(
                columns={
                    "code": "Code",
                    "name_zh": "Name(ZH)",
                    "name_en": "Name(EN)",
                    "category": "Category",
                    "nav": "NAV",
                    "est_nav": "Est NAV",
                    "day_change_pct": "Day %",
                }
            )
        )

    with compat_container(border=True):
        st.subheader(L["holdings_header"])
        st.caption(L["edit_tip"])
        st.caption(L["delete_help"])

        with st.form("add_position_form", clear_on_submit=True):
            st.markdown(f"**{L['add_position']}**")
            fund_snapshot["add_label"] = fund_snapshot["code"] + " | " + (
                fund_snapshot["name_en"] if language == "en" else fund_snapshot["name_zh"]
            )
            selected_label = st.selectbox("Code", fund_snapshot["add_label"].tolist(), key="add_code")
            selected_code = selected_label.split(" | ")[0]
            selected_row = fund_snapshot[fund_snapshot["code"] == selected_code].iloc[0]
            default_name = selected_row["name_en"] if language == "en" else selected_row["name_zh"]
            col1, col2 = st.columns(2)
            with col1:
                shares = st.number_input("Shares", min_value=0.0, value=1000.0, step=100.0)
            with col2:
                cost_per_share = st.number_input("Cost/Share", min_value=0.0, value=float(selected_row["nav"]), step=0.01)
            name = st.text_input("Name", value=default_name)
            add_submitted = st.form_submit_button(L["add_position"])
            if add_submitted:
                new_row = pd.DataFrame([
                    {"code": selected_code, "name": name, "shares": shares, "cost_per_share": cost_per_share}
                ])
                st.session_state.positions = pd.concat([st.session_state.positions, new_row], ignore_index=True)
                st.success("Added." if language == "en" else "已新增持仓。")

        c1, c2 = st.columns(2)
        with c1:
            if st.button(L["use_default"], use_container_width=True):
                st.session_state.positions = provider.get_default_positions()
        with c2:
            if st.button(L["clear_positions"], use_container_width=True):
                st.session_state.positions = ensure_position_schema(pd.DataFrame(columns=["code", "name", "shares", "cost_per_share"]))

        st.session_state.positions = render_positions_editor(ensure_position_schema(st.session_state.positions), language)

positions_clean = ensure_position_schema(st.session_state.positions)
positions_clean = positions_clean[(positions_clean["code"].str.strip() != "") & (positions_clean["shares"] > 0)]
position_metrics = calc_position_metrics(positions_clean, fund_snapshot)
kpis = calc_portfolio_kpis(position_metrics)

with right_col:
    with compat_container(border=True):
        st.caption(L["right_panel"])
        st.subheader(L["source_header"])
        meta = provider.get_meta()
        source_name = meta.source_label_en if language == "en" else meta.source_label_zh
        note = meta.notes_en if language == "en" else meta.notes_zh
        s1, s2, s3 = st.columns(3)
        s1.metric(L["source_label"], source_name)
        s2.metric(L["source_mode"], meta.data_mode)
        s3.metric(L["source_time"], meta.updated_at.strftime("%Y-%m-%d %H:%M:%S"))
        st.caption(note)
        if meta.data_mode != "live":
            st.warning(L["mock_flag"])

    with compat_container(border=True):
        st.subheader(L["kpi_header"])
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(L["kpi_total_cost"], money(kpis["total_cost"]))
        k2.metric(L["kpi_market"], money(kpis["total_market"]))
        k3.metric(L["kpi_today_profit"], money(kpis["today_est_profit"]))
        k4.metric(L["kpi_return"], pct(kpis["total_return_rate"]))

    with compat_container(border=True):
        st.subheader(L["analysis_header"])
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

    with compat_container(border=True):
        st.subheader(L["charts_header"])
        trend_col, bar_col = st.columns(2)

        with trend_col:
            st.markdown(f"**{L['chart_nav']}**")
            fund_snapshot["label"] = fund_snapshot["code"] + " | " + (
                fund_snapshot["name_en"] if language == "en" else fund_snapshot["name_zh"]
            )
            selected_label = st.selectbox(L["chart_fund"], fund_snapshot["label"].tolist())
            chart_code = selected_label.split(" | ")[0]
            trend_df = provider.get_trend(chart_code, days=120)
            name_row = fund_snapshot[fund_snapshot["code"] == chart_code].iloc[0]
            display_name = name_row["name_en"] if language == "en" else name_row["name_zh"]

            fig_trend = go.Figure()
            fig_trend.add_trace(
                go.Scatter(
                    x=trend_df["date"],
                    y=trend_df["nav"],
                    mode="lines",
                    name="NAV",
                    hovertemplate=f"{display_name} ({chart_code})<br>Date=%{{x}}<br>NAV=%{{y:.4f}}<extra></extra>",
                )
            )
            fig_trend.add_trace(
                go.Scatter(
                    x=trend_df["date"],
                    y=trend_df["est_nav"],
                    mode="lines",
                    name="Est NAV",
                    hovertemplate=f"{display_name} ({chart_code})<br>Date=%{{x}}<br>Est NAV=%{{y:.4f}}<extra></extra>",
                )
            )
            fig_trend.update_layout(
                height=340,
                margin=dict(l=20, r=20, t=10, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                xaxis_title=None,
                yaxis_title=None,
                template=plotly_template,
            )
            fig_trend.update_xaxes(nticks=6)
            safe_plotly_chart(fig_trend)

        with bar_col:
            st.markdown(f"**{L['chart_profit']}**")
            if position_metrics.empty:
                st.warning(L["empty_holdings"])
            else:
                chart_data = position_metrics.copy()
                chart_data["display_name"] = chart_data.apply(
                    lambda row: f"{row['name']} ({row['code']})",
                    axis=1,
                )
                fig_bar = px.bar(
                    chart_data,
                    x="display_name",
                    y="today_est_profit",
                    color="today_est_profit",
                    color_continuous_scale="RdYlGn",
                    hover_data={
                        "display_name": False,
                        "code": True,
                        "name": True,
                        "shares": ":.0f",
                        "today_est_profit": ":.2f",
                        "profit_rate": ":.2%",
                    },
                )
                fig_bar.update_layout(
                    height=340,
                    margin=dict(l=20, r=20, t=10, b=20),
                    xaxis_title=None,
                    yaxis_title=None,
                    template=plotly_template,
                )
                fig_bar.update_xaxes(tickangle=-20)
                safe_plotly_chart(fig_bar)

    with compat_container(border=True):
        st.subheader(L["insights_header"])
        for insight in generate_auto_insights(position_metrics, language=language):
            st.write(f"- {insight}")
