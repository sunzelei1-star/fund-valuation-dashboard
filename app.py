from __future__ import annotations

from contextlib import contextmanager

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data.providers.registry import get_fund_data_provider
from utils.analysis import REQUIRED_METRIC_COLUMNS, calc_account_kpis, calc_portfolio_kpis, calc_position_metrics, generate_auto_insights

st.set_page_config(page_title="Fund Valuation Dashboard", page_icon="📊", layout="wide")

I18N = {
    "zh": {
        "app_title": "基金估值与持仓收益分析 Dashboard",
        "app_subtitle": "双栏基金分析产品：真实历史趋势、多账户、双持仓输入模式",
        "lang_label": "语言",
        "theme_tip": "提示：使用右上角系统主题切换可体验 Light / Dark 模式。",
        "query_header": "基金查询与筛选",
        "query_input": "输入基金代码、名称或分类",
        "query_table": "基金估值结果",
        "holdings_header": "持仓与账户管理",
        "add_position": "新增基金到持仓",
        "clear_positions": "清空当前账户",
        "use_default": "一键加载示例持仓",
        "kpi_header": "KPI 核心指标",
        "analysis_header": "持仓收益分析",
        "charts_header": "图表区",
        "chart_nav": "基金净值 / 估值趋势",
        "chart_profit": "持仓今日预估收益分布",
        "chart_fund": "图表基金",
        "chart_date": "日期",
        "chart_nav_axis": "净值",
        "chart_today_pnl": "今日预估收益",
        "hover_full_name": "基金全称",
        "source_header": "数据来源说明",
        "source_label": "数据来源",
        "source_mode": "数据模式",
        "source_time": "更新时间(UTC)",
        "source_valuation": "估值语义",
        "source_est_coverage": "官方估值覆盖率",
        "source_approx_ratio": "近似估值持仓占比",
        "official_est": "official_estimate（官方估值）",
        "approx_est": "approx_from_change（涨跌幅近似）",
        "nav_snapshot": "nav_snapshot（净值快照）",
        "trend_degrade": "该基金缺失估值历史，趋势图仅展示净值历史（Est NAV=NAV）。",
        "table_code": "代码",
        "table_name": "名称",
        "table_nav": "净值",
        "table_est_nav": "估值",
        "table_day_pct": "日涨跌",
        "table_today_pnl": "今日预估收益",
        "table_total_pnl": "累计收益",
        "table_return": "收益率",
        "table_mode": "录入模式",
        "table_invest": "持有金额",
        "table_profit_input": "持有收益",
        "table_shares": "推导份额",
        "table_cost": "推导成本单价",
        "insights_header": "自动分析结论",
        "account_header": "账户",
        "account_all": "全部账户汇总",
    },
    "en": {
        "app_title": "Fund Valuation & Portfolio Analytics Dashboard",
        "app_subtitle": "Two-column fund analytics app with real trend, multi-account and dual input modes",
        "lang_label": "Language",
        "theme_tip": "Tip: switch themes via Streamlit settings.",
        "query_header": "Fund Lookup & Filter",
        "query_input": "Search by code, name, or category",
        "query_table": "Fund valuation results",
        "holdings_header": "Holdings & Account Management",
        "add_position": "Add fund to holdings",
        "clear_positions": "Clear current account",
        "use_default": "Load sample holdings",
        "kpi_header": "KPI Overview",
        "analysis_header": "Holdings PnL Analysis",
        "charts_header": "Charts",
        "chart_nav": "Fund NAV / Est NAV Trend",
        "chart_profit": "Today's estimated PnL by position",
        "chart_fund": "Chart fund",
        "chart_date": "Date",
        "chart_nav_axis": "Value",
        "chart_today_pnl": "Today Est PnL",
        "hover_full_name": "Full name",
        "source_header": "Data Source",
        "source_label": "Source",
        "source_mode": "Mode",
        "source_time": "Updated at (UTC)",
        "source_valuation": "Valuation semantics",
        "source_est_coverage": "Official estimate coverage",
        "source_approx_ratio": "Approx valuation position ratio",
        "official_est": "official_estimate",
        "approx_est": "approx_from_change",
        "nav_snapshot": "nav_snapshot",
        "trend_degrade": "Estimate history is unavailable; chart falls back to NAV-only history (Est NAV=NAV).",
        "table_code": "Code",
        "table_name": "Name",
        "table_nav": "NAV",
        "table_est_nav": "Est NAV",
        "table_day_pct": "Day %",
        "table_today_pnl": "Today Est PnL",
        "table_total_pnl": "Total PnL",
        "table_return": "Return",
        "table_mode": "Input mode",
        "table_invest": "Holding amount",
        "table_profit_input": "Holding profit",
        "table_shares": "Derived shares",
        "table_cost": "Derived cost/share",
        "insights_header": "Automated Insights",
        "account_header": "Accounts",
        "account_all": "All accounts",
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


def valuation_text(kind: str | None, language: str) -> str:
    mapping = {
        "official_estimate": I18N[language]["official_est"],
        "approx_from_change": I18N[language]["approx_est"],
        "nav_snapshot": I18N[language]["nav_snapshot"],
    }
    return mapping.get(str(kind), I18N[language]["nav_snapshot"])


def money(x: float) -> str:
    return f"¥{x:,.2f}"


def pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def normalize_positions(df: pd.DataFrame, account: str | None = None) -> pd.DataFrame:
    wanted = ["account", "code", "name", "input_mode", "shares", "cost_per_share", "invested_amount", "holding_profit"]
    data = df.copy()
    for col in wanted:
        if col not in data.columns:
            data[col] = "" if col in {"account", "code", "name", "input_mode"} else 0.0
    if account is not None:
        data["account"] = account
    data["account"] = data["account"].astype(str)
    data["code"] = data["code"].astype(str)
    data["name"] = data["name"].astype(str)
    data["input_mode"] = data["input_mode"].replace("", "pro").fillna("pro")
    for col in ["shares", "cost_per_share", "invested_amount", "holding_profit"]:
        data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0.0)
    return data[wanted]


def split_accounts(positions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if positions.empty:
        return {"主账户": normalize_positions(pd.DataFrame(), account="主账户")}
    out = {}
    for acc, chunk in positions.groupby("account"):
        out[str(acc)] = normalize_positions(chunk, account=str(acc))
    return out


provider = get_fund_data_provider()
plotly_template = "plotly_dark" if st.get_option("theme.base") == "dark" else "plotly_white"
language = st.selectbox(I18N["zh"]["lang_label"], ["zh", "en"], format_func=lambda x: "中文" if x == "zh" else "English")
L = I18N[language]
st.title(L["app_title"])
st.caption(L["app_subtitle"])

try:
    fund_snapshot = provider.get_snapshots()
except Exception:
    from data.providers.mock_provider import LocalMockFundProvider

    provider = LocalMockFundProvider()
    fund_snapshot = provider.get_snapshots()

if "accounts" not in st.session_state:
    st.session_state.accounts = split_accounts(normalize_positions(provider.get_default_positions()))
if "active_account" not in st.session_state:
    st.session_state.active_account = next(iter(st.session_state.accounts.keys()))

left_col, right_col = st.columns([1.12, 1.35], gap="large")

with left_col:
    with compat_container(border=True):
        st.subheader(L["query_header"])
        query = st.text_input(L["query_input"], placeholder="161725 / 白酒 / consumer")
        fund_results = provider.search(query) if query else fund_snapshot
        show_cols = ["code", "name_zh", "name_en", "category", "nav", "est_nav", "day_change_pct", "valuation_kind", "snapshot_time"]
        show_df = fund_results[[c for c in show_cols if c in fund_results.columns]].copy()
        if "valuation_kind" in show_df.columns:
            show_df["valuation_kind"] = show_df["valuation_kind"].map(lambda x: valuation_text(x, language))
        st.dataframe(show_df, hide_index=True, use_container_width=True)

    with compat_container(border=True):
        st.subheader(L["holdings_header"])
        account_names = list(st.session_state.accounts.keys())
        selected_view = st.selectbox(
            L["account_header"],
            [L["account_all"]] + account_names,
            index=(account_names.index(st.session_state.active_account) + 1 if st.session_state.active_account in account_names else 0),
        )
        if selected_view != L["account_all"]:
            st.session_state.active_account = selected_view

        c1, c2 = st.columns([2, 1])
        with c1:
            new_account = st.text_input("新增账户" if language == "zh" else "New account")
        with c2:
            if st.button("新增" if language == "zh" else "Add", use_container_width=True) and new_account.strip():
                if new_account.strip() not in st.session_state.accounts:
                    st.session_state.accounts[new_account.strip()] = normalize_positions(pd.DataFrame(), account=new_account.strip())
                    st.session_state.active_account = new_account.strip()

        if selected_view != L["account_all"]:
            if st.button("删除当前账户" if language == "zh" else "Delete account", use_container_width=True):
                if len(st.session_state.accounts) > 1:
                    st.session_state.accounts.pop(st.session_state.active_account, None)
                    st.session_state.active_account = next(iter(st.session_state.accounts.keys()))

            with st.form("add_position_form", clear_on_submit=True):
                st.markdown(f"**{L['add_position']}**")
                fund_snapshot["add_label"] = fund_snapshot["code"] + " | " + fund_snapshot["name_zh"]
                selected_label = st.selectbox("基金" if language == "zh" else "Fund", fund_snapshot["add_label"].tolist())
                selected_code = selected_label.split(" | ")[0]
                selected_row = fund_snapshot[fund_snapshot["code"] == selected_code].iloc[0]
                mode = st.radio("录入模式" if language == "zh" else "Input mode", ["simple", "pro"], horizontal=True, index=0)
                name = st.text_input(L["table_name"], value=str(selected_row["name_zh"]))
                if mode == "pro":
                    shares = st.number_input("持仓份额" if language == "zh" else "Shares", min_value=0.0, value=1000.0, step=100.0)
                    cost_per_share = st.number_input("成本单价" if language == "zh" else "Cost/share", min_value=0.0, value=float(selected_row["nav"]), step=0.01)
                    invested_amount, holding_profit = 0.0, 0.0
                else:
                    invested_amount = st.number_input("持有金额" if language == "zh" else "Holding amount", min_value=0.0, value=3000.0, step=100.0)
                    holding_profit = st.number_input("持有收益" if language == "zh" else "Holding profit", value=120.0, step=10.0)
                    shares, cost_per_share = 0.0, 0.0
                if st.form_submit_button(L["add_position"]):
                    new_row = pd.DataFrame([
                        {
                            "account": st.session_state.active_account,
                            "code": selected_code,
                            "name": name,
                            "input_mode": mode,
                            "shares": shares,
                            "cost_per_share": cost_per_share,
                            "invested_amount": invested_amount,
                            "holding_profit": holding_profit,
                        }
                    ])
                    st.session_state.accounts[st.session_state.active_account] = pd.concat(
                        [normalize_positions(st.session_state.accounts[st.session_state.active_account]), new_row], ignore_index=True
                    )

            if st.button(L["clear_positions"], use_container_width=True):
                st.session_state.accounts[st.session_state.active_account] = normalize_positions(pd.DataFrame(), account=st.session_state.active_account)
            if st.button(L["use_default"], use_container_width=True):
                st.session_state.accounts = split_accounts(normalize_positions(provider.get_default_positions()))

            editable = normalize_positions(st.session_state.accounts[st.session_state.active_account], account=st.session_state.active_account)
            st.caption("用户输入字段：input_mode / shares / cost_per_share / invested_amount / holding_profit" if language == "zh" else "User input fields: input_mode / shares / cost_per_share / invested_amount / holding_profit")
            st.session_state.accounts[st.session_state.active_account] = st.data_editor(
                editable,
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                key=f"editor_{st.session_state.active_account}",
            )

all_positions = pd.concat([normalize_positions(df, account=acc) for acc, df in st.session_state.accounts.items()], ignore_index=True)
all_positions = normalize_positions(all_positions)
all_positions = all_positions[all_positions["code"].str.strip() != ""]

if selected_view == L["account_all"]:
    current_positions = all_positions
else:
    current_positions = all_positions[all_positions["account"] == st.session_state.active_account]

position_metrics = calc_position_metrics(current_positions, fund_snapshot)
kpis = calc_portfolio_kpis(position_metrics)
account_kpis = calc_account_kpis(calc_position_metrics(all_positions, fund_snapshot))

with right_col:
    with compat_container(border=True):
        st.subheader(L["source_header"])
        meta = provider.get_meta()
        s1, s2, s3 = st.columns(3)
        s1.metric(L["source_label"], meta.source_label_zh if language == "zh" else meta.source_label_en)
        s2.metric(L["source_mode"], meta.data_mode)
        s3.metric(L["source_time"], meta.updated_at.strftime("%Y-%m-%d %H:%M:%S"))
        official_ratio = float((fund_snapshot.get("valuation_kind", pd.Series(dtype=str)) == "official_estimate").mean() or 0.0)
        approx_ratio = kpis["approx_position_ratio"]
        s4, s5, s6 = st.columns(3)
        dom = "official_estimate" if official_ratio >= 0.5 else "approx_from_change"
        s4.metric(L["source_valuation"], valuation_text(dom, language))
        s5.metric(L["source_est_coverage"], f"{official_ratio * 100:.1f}%")
        s6.metric(L["source_approx_ratio"], f"{approx_ratio * 100:.1f}%")

    with compat_container(border=True):
        st.subheader(L["kpi_header"])
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("总成本" if language == "zh" else "Total Cost", money(kpis["total_cost"]))
        k2.metric("当前市值" if language == "zh" else "Market Value", money(kpis["total_market"]))
        k3.metric("今日预估收益" if language == "zh" else "Today Est PnL", money(kpis["today_est_profit"]))
        k4.metric("累计收益率" if language == "zh" else "Return", pct(kpis["total_return_rate"]))

    with compat_container(border=True):
        st.subheader(L["analysis_header"])
        st.caption("系统推导字段：nav / est_nav / today_est_profit / total_profit / profit_rate 等" if language == "zh" else "System-derived fields: nav / est_nav / today_est_profit / total_profit / profit_rate, etc.")
        analysis_cols = [
            "account",
            "code",
            "name",
            "input_mode",
            "invested_amount",
            "holding_profit",
            "shares",
            "cost_per_share",
            "nav",
            "est_nav",
            "valuation_kind",
            "snapshot_time",
            "today_est_profit",
            "total_profit",
            "profit_rate",
        ]
        metrics_for_view = position_metrics.copy()
        for col in REQUIRED_METRIC_COLUMNS:
            if col not in metrics_for_view.columns:
                metrics_for_view[col] = 0.0 if col not in {"account", "code", "name", "input_mode", "valuation_kind", "snapshot_time"} else ""
        analysis_df = metrics_for_view.reindex(columns=analysis_cols, fill_value=0.0).copy()
        analysis_df["valuation_kind"] = analysis_df["valuation_kind"].map(lambda x: valuation_text(x, language))
        st.dataframe(analysis_df, hide_index=True, use_container_width=True)
        if not account_kpis.empty:
            st.markdown("**账户 KPI**" if language == "zh" else "**Account KPI**")
            account_kpis = account_kpis.sort_values("today_est_profit", ascending=False).reset_index(drop=True)
            st.dataframe(account_kpis, hide_index=True, use_container_width=True)
            fig_acc = px.bar(
                account_kpis,
                x="account",
                y="total_return_rate",
                color="today_est_profit",
                color_continuous_scale="RdYlGn",
                title="账户收益率对比" if language == "zh" else "Account return-rate comparison",
            )
            fig_acc.update_layout(template=plotly_template, height=260, coloraxis_showscale=False)
            st.plotly_chart(fig_acc, use_container_width=True)

    with compat_container(border=True):
        st.subheader(L["charts_header"])
        trend_col, bar_col = st.columns(2)
        with trend_col:
            st.markdown(f"**{L['chart_nav']}**")
            labels = (fund_snapshot["code"] + " | " + fund_snapshot["name_zh"]).tolist()
            selected_label = st.selectbox(L["chart_fund"], labels)
            chart_code = selected_label.split(" | ")[0]
            trend_df = provider.get_trend(chart_code, days=120)
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(x=trend_df["date"], y=trend_df["nav"], mode="lines", name="NAV"))
            fig_trend.add_trace(go.Scatter(x=trend_df["date"], y=trend_df["est_nav"], mode="lines", name="Est NAV", line=dict(dash="dot")))
            fig_trend.update_layout(template=plotly_template, height=340, xaxis_title=L["chart_date"], yaxis_title=L["chart_nav_axis"])
            st.plotly_chart(fig_trend, use_container_width=True)
            if not bool(trend_df.get("has_est_history", pd.Series([True])).iloc[0]):
                st.info(L["trend_degrade"])

        with bar_col:
            st.markdown(f"**{L['chart_profit']}**")
            if position_metrics.empty:
                st.warning("暂无持仓" if language == "zh" else "No holdings")
            else:
                chart_data = position_metrics.copy()
                chart_data["valuation_kind_label"] = chart_data["valuation_kind"].map(lambda x: valuation_text(x, language))
                fig_bar = px.bar(chart_data, x="name", y="today_est_profit", color="today_est_profit", hover_data=["account", "code", "valuation_kind_label", "snapshot_time"])
                fig_bar.update_layout(template=plotly_template, height=340, yaxis_title=L["chart_today_pnl"], coloraxis_showscale=False)
                st.plotly_chart(fig_bar, use_container_width=True)

    with compat_container(border=True):
        st.subheader(L["insights_header"])
        for insight in generate_auto_insights(position_metrics, language=language):
            st.write(f"- {insight}")
