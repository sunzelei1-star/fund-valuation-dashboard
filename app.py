from __future__ import annotations

from contextlib import contextmanager

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data.providers.registry import get_fund_data_provider
from utils.analysis import REQUIRED_METRIC_COLUMNS, calc_account_kpis, calc_portfolio_kpis, calc_position_metrics, generate_auto_insights

st.set_page_config(
    page_title="养基智析 | 基金估值与持仓分析",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

I18N = {
    "zh": {
        "app_title": "养基智析 · 基金估值与持仓分析",
        "app_subtitle": "面向真实投资场景的基金分析 Dashboard，支持真实趋势、Live 估值、多账户与双模式持仓录入。",
        "hero_badge": "公网展示版 / Portfolio Ready",
        "hero_cap_1": "真实历史趋势",
        "hero_cap_2": "AKShare Live 估值",
        "hero_cap_3": "多账户分析",
        "hero_cap_4": "Simple / Pro 双模式持仓",
        "lang_label": "语言",
        "query_header": "基金查询",
        "query_input": "输入基金代码、名称或分类",
        "query_table": "基金估值结果",
        "holdings_header": "持仓与账户管理",
        "add_position": "新增基金到持仓",
        "clear_positions": "清空当前账户",
        "use_default": "加载示例持仓",
        "kpi_header": "KPI 总览",
        "analysis_header": "持仓分析明细",
        "charts_header": "历史趋势与收益分布",
        "chart_nav": "基金净值 / 估值趋势",
        "chart_profit": "持仓今日预估收益分布",
        "chart_fund": "图表基金",
        "chart_date": "日期",
        "chart_nav_axis": "净值",
        "chart_today_pnl": "今日预估收益",
        "hover_full_name": "基金全称",
        "source_header": "数据来源与估值说明",
        "source_label": "数据来源",
        "source_mode": "数据模式",
        "source_time": "更新时间(UTC)",
        "source_valuation": "主估值语义",
        "source_est_coverage": "官方估值覆盖率",
        "source_approx_ratio": "近似估值持仓占比",
        "official_est": "官方估值（official_estimate）",
        "approx_est": "近似估值（approx_from_change）",
        "nav_snapshot": "净值快照（nav_snapshot）",
        "trend_degrade": "该基金暂缺估值历史，趋势图已自动降级为净值历史（Est NAV = NAV）。",
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
        "account_header": "账户视角",
        "account_all": "全部账户汇总",
        "active_account": "当前编辑账户",
        "add_account": "新增账户",
        "add_account_placeholder": "如：主账户 / 支付宝 / 家庭账户",
        "new_account": "新增账户名",
        "delete_account": "删除当前账户",
        "fund_selector": "基金",
        "input_mode": "录入模式",
        "input_mode_simple": "simple（金额+收益）",
        "input_mode_pro": "pro（份额+成本）",
        "input_fields": "用户输入字段",
        "system_fields": "系统推导字段",
        "no_holdings": "暂无持仓",
        "product_disclaimer": "说明：本应用用于基金估值与持仓分析展示，不构成投资建议；估值可能与最终净值存在偏差。",
    },
    "en": {
        "app_title": "FundPilot · Valuation & Portfolio Analytics",
        "app_subtitle": "A portfolio-ready fund analytics dashboard with real trend, live valuation, multi-account and dual input modes.",
        "hero_badge": "Portfolio Ready",
        "hero_cap_1": "Real Trend History",
        "hero_cap_2": "AKShare Live Valuation",
        "hero_cap_3": "Multi-account Analysis",
        "hero_cap_4": "Simple / Pro Dual Input",
        "lang_label": "Language",
        "query_header": "Fund Lookup",
        "query_input": "Search by code, name, or category",
        "query_table": "Fund valuation results",
        "holdings_header": "Holdings & Account Management",
        "add_position": "Add fund to holdings",
        "clear_positions": "Clear current account",
        "use_default": "Load sample holdings",
        "kpi_header": "KPI Overview",
        "analysis_header": "Position Analysis",
        "charts_header": "Trend & Return Distribution",
        "chart_nav": "Fund NAV / Est NAV Trend",
        "chart_profit": "Today's estimated PnL by position",
        "chart_fund": "Chart fund",
        "chart_date": "Date",
        "chart_nav_axis": "Value",
        "chart_today_pnl": "Today Est PnL",
        "hover_full_name": "Full name",
        "source_header": "Data Source & Valuation Notes",
        "source_label": "Data source",
        "source_mode": "Data mode",
        "source_time": "Updated at (UTC)",
        "source_valuation": "Primary valuation type",
        "source_est_coverage": "Official estimate coverage",
        "source_approx_ratio": "Approx valuation position ratio",
        "official_est": "official_estimate",
        "approx_est": "approx_from_change",
        "nav_snapshot": "nav_snapshot",
        "trend_degrade": "Estimate history is unavailable; chart falls back to NAV-only history (Est NAV = NAV).",
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
        "account_header": "Account view",
        "account_all": "All accounts",
        "active_account": "Editing account",
        "add_account": "Add account",
        "add_account_placeholder": "e.g. Main / Alipay / Family",
        "new_account": "New account name",
        "delete_account": "Delete current account",
        "fund_selector": "Fund",
        "input_mode": "Input mode",
        "input_mode_simple": "simple (amount + pnl)",
        "input_mode_pro": "pro (shares + cost)",
        "input_fields": "User input fields",
        "system_fields": "System-derived fields",
        "no_holdings": "No holdings",
        "product_disclaimer": "Note: This app is for fund valuation and holdings analysis only, not investment advice. Estimated values may differ from official settlements.",
    },
}


def inject_styles() -> None:
    is_dark = st.get_option("theme.base") == "dark"
    colors = {
        "app_bg": "#0b1220" if is_dark else "#f5f7fb",
        "card_bg": "#111a2e" if is_dark else "#ffffff",
        "card_border": "#25324a" if is_dark else "#e6ebf2",
        "text_primary": "#e6edf7" if is_dark else "#0f172a",
        "text_secondary": "#b8c5d8" if is_dark else "#475569",
        "input_bg": "#0f1a30" if is_dark else "#ffffff",
        "input_border": "#334155" if is_dark else "#dbe3ef",
        "input_focus": "#60a5fa" if is_dark else "#2563eb",
        "table_head_bg": "#17233a" if is_dark else "#f8fafc",
        "table_head_text": "#dbe7fb" if is_dark else "#334155",
        "table_body_bg": "#111a2e" if is_dark else "#ffffff",
        "button_bg": "#2563eb" if is_dark else "#1d4ed8",
        "button_text": "#f8fbff",
        "button_hover": "#1d4ed8" if is_dark else "#1e40af",
    }
    st.markdown(
        f"""
        <style>
        .stApp {{ background: {colors["app_bg"]}; color: {colors["text_primary"]}; }}
        .block-container {{ padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1320px; }}
        [data-testid="stMetric"] {{
            background: {colors["card_bg"]}; border: 1px solid {colors["card_border"]}; border-radius: 14px;
            padding: 14px 16px; box-shadow: 0 2px 8px rgba(15, 23, 42, 0.10);
        }}
        [data-testid="stMetricLabel"] {{ color: {colors["text_secondary"]}; font-weight: 600; }}
        [data-testid="stMetricValue"] {{ color: {colors["text_primary"]}; font-weight: 700; }}
        [data-testid="stMetricDelta"] {{ color: {colors["text_secondary"]}; }}
        .panel-card {{
            background: {colors["card_bg"]}; border: 1px solid {colors["card_border"]}; border-radius: 16px;
            padding: 16px 18px; box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04); margin-bottom: 0.9rem;
        }}
        .hero-card {{
            background: linear-gradient(135deg, #0f4c81 0%, #0c6aa6 52%, #1393c7 100%);
            border-radius: 18px; color: #f8fbff; padding: 1.1rem 1.25rem; margin-bottom: 0.75rem;
            box-shadow: 0 6px 18px rgba(14, 76, 129, 0.22);
        }}
        .hero-badge {{
            display: inline-block; font-size: 0.72rem; font-weight: 700; letter-spacing: .02em;
            background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.3);
            border-radius: 999px; padding: 4px 10px; margin-bottom: .35rem;
        }}
        .hero-cap-row {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 10px; }}
        .hero-cap {{
            background: rgba(255,255,255,.14); border-radius: 10px; padding: 7px 10px;
            border: 1px solid rgba(255,255,255,.2); font-size: .83rem;
        }}
        .hint {{ color: {colors["text_secondary"]}; font-size: .82rem; margin-top: .35rem; }}
        .section-title {{ font-size: 1rem; font-weight: 700; color: {colors["text_primary"]}; margin-bottom: .4rem; }}
        .footnote {{ color: {colors["text_secondary"]}; font-size: .84rem; padding: .35rem .1rem 0 .1rem; }}
        [data-testid="stCaptionContainer"], label, p, li {{ color: {colors["text_primary"]}; }}
        div[data-testid="stDataFrame"] div[role="columnheader"] {{
            background: {colors["table_head_bg"]} !important; color: {colors["table_head_text"]} !important; font-weight: 600 !important;
        }}
        div[data-testid="stDataFrame"] div[role="gridcell"],
        div[data-testid="stDataEditor"] div[role="gridcell"] {{
            color: {colors["text_primary"]} !important;
            background: {colors["table_body_bg"]} !important;
        }}
        div[data-testid="stDataEditor"] [data-testid="stDataFrame"] {{
            border: 1px solid {colors["card_border"]}; border-radius: 12px;
        }}
        div[data-testid="stDataEditor"] div[role="columnheader"] {{
            background: {colors["table_head_bg"]} !important; color: {colors["table_head_text"]} !important; font-weight: 600 !important;
        }}
        .stTextInput > div > div input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div, .stTextArea textarea {{
            border-radius: 10px !important; border-color: {colors["input_border"]} !important;
            background: {colors["input_bg"]} !important; color: {colors["text_primary"]} !important;
        }}
        .stTextInput > div > div input::placeholder, .stTextArea textarea::placeholder {{
            color: {colors["text_secondary"]} !important; opacity: 0.9 !important;
        }}
        .stTextInput > div > div input:focus, .stNumberInput input:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within {{
            border-color: {colors["input_focus"]} !important;
            box-shadow: 0 0 0 1px {colors["input_focus"]} !important;
        }}
        .stSelectbox span, .stRadio label, .stMarkdown, .stCaption {{
            color: {colors["text_primary"]} !important;
        }}
        .stButton > button {{
            border-radius: 10px !important;
            background: {colors["button_bg"]} !important;
            color: {colors["button_text"]} !important;
            border: 1px solid {colors["button_bg"]} !important;
            font-weight: 600 !important;
        }}
        .stButton > button:hover {{
            background: {colors["button_hover"]} !important;
            border-color: {colors["button_hover"]} !important;
        }}
        .modebar {{ display: none !important; }}

        </style>
        """,
        unsafe_allow_html=True,
    )


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


def build_fund_name_lookup(fund_snapshot: pd.DataFrame, language: str) -> dict[str, str]:
    primary = "name_zh" if language == "zh" else "name_en"
    fallback = "name_en" if language == "zh" else "name_zh"
    base = fund_snapshot.copy()
    for col in [primary, fallback, "code"]:
        if col not in base.columns:
            base[col] = ""
    base[primary] = base[primary].fillna("").astype(str).str.strip()
    base[fallback] = base[fallback].fillna("").astype(str).str.strip()
    base["display_name"] = base[primary]
    empty_mask = base["display_name"] == ""
    base.loc[empty_mask, "display_name"] = base.loc[empty_mask, fallback]
    empty_mask = base["display_name"] == ""
    base.loc[empty_mask, "display_name"] = base.loc[empty_mask, "code"].astype(str)
    return dict(zip(base["code"].astype(str), base["display_name"]))


def localize_fund_name_column(
    df: pd.DataFrame, lookup: dict[str, str], code_col: str = "code", name_col: str = "name"
) -> pd.DataFrame:
    out = df.copy()
    if code_col not in out.columns:
        return out
    localized = out[code_col].astype(str).map(lookup)
    if name_col in out.columns:
        out[name_col] = localized.fillna(out[name_col].astype(str))
    else:
        out[name_col] = localized.fillna(out[code_col].astype(str))
    return out


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


inject_styles()
provider = get_fund_data_provider()
is_dark_theme = st.get_option("theme.base") == "dark"
plotly_template = "plotly_dark" if is_dark_theme else "plotly_white"
plotly_font_color = "#dbe7fb" if is_dark_theme else "#1e293b"
plotly_axis_grid = "#334155" if is_dark_theme else "#dbe3ef"
plotly_paper_bg = "#111a2e" if is_dark_theme else "#ffffff"
plotly_hover_bg = "#1e293b" if is_dark_theme else "#f8fafc"
plotly_hover_font = "#f8fbff" if is_dark_theme else "#0f172a"
plotly_config = {
    "displayModeBar": False,
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "zoom",
        "pan",
        "select",
        "lasso2d",
        "autoScale",
        "resetScale",
        "toImage",
        "hoverCompareCartesian",
        "hoverClosestCartesian",
    ],
    "responsive": True,
}
language = st.selectbox(I18N["zh"]["lang_label"], ["zh", "en"], format_func=lambda x: "中文" if x == "zh" else "English")
L = I18N[language]

st.markdown(
    f"""
    <div class="hero-card">
      <div class="hero-badge">{L['hero_badge']}</div>
      <h2 style="margin:0; color:#fff; font-size:1.6rem;">{L['app_title']}</h2>
      <p style="margin:.35rem 0 0 0; color:rgba(248,251,255,.95);">{L['app_subtitle']}</p>
      <div class="hero-cap-row">
        <div class="hero-cap">{L['hero_cap_1']}</div>
        <div class="hero-cap">{L['hero_cap_2']}</div>
        <div class="hero-cap">{L['hero_cap_3']}</div>
        <div class="hero-cap">{L['hero_cap_4']}</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

try:
    fund_snapshot = provider.get_snapshots()
except Exception:
    from data.providers.mock_provider import LocalMockFundProvider

    provider = LocalMockFundProvider()
    fund_snapshot = provider.get_snapshots()

fund_name_lookup = build_fund_name_lookup(fund_snapshot, language)

if "accounts" not in st.session_state:
    st.session_state.accounts = split_accounts(normalize_positions(provider.get_default_positions()))
if "active_account" not in st.session_state:
    st.session_state.active_account = next(iter(st.session_state.accounts.keys()))

left_col, right_col = st.columns([1.08, 1.42], gap="large")

with left_col:
    with compat_container(border=False):
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="section-title">{L["query_header"]}</div>', unsafe_allow_html=True)
        query = st.text_input(L["query_input"], placeholder="161725 / 白酒 / consumer")
        fund_results = provider.search(query) if query else fund_snapshot
        show_cols = ["code", "category", "nav", "est_nav", "day_change_pct", "valuation_kind", "snapshot_time"]
        show_df = fund_results[[c for c in show_cols if c in fund_results.columns]].copy()
        show_df.insert(1, "name", fund_results["code"].astype(str).map(fund_name_lookup).fillna(fund_results.get("name_zh", "")))
        if "valuation_kind" in show_df.columns:
            show_df["valuation_kind"] = show_df["valuation_kind"].map(lambda x: valuation_text(x, language))
        st.dataframe(
            show_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "name": st.column_config.TextColumn(L["table_name"]),
                "nav": st.column_config.NumberColumn(L["table_nav"], format="%.4f"),
                "est_nav": st.column_config.NumberColumn(L["table_est_nav"], format="%.4f"),
                "day_change_pct": st.column_config.NumberColumn(L["table_day_pct"], format="%.2f%%"),
            },
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with compat_container(border=False):
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="section-title">{L["holdings_header"]}</div>', unsafe_allow_html=True)

        account_names = list(st.session_state.accounts.keys())
        selected_view = st.radio(
            L["account_header"],
            [L["account_all"]] + account_names,
            horizontal=True,
            index=(account_names.index(st.session_state.active_account) + 1 if st.session_state.active_account in account_names else 0),
        )
        if selected_view != L["account_all"]:
            st.session_state.active_account = selected_view

        st.caption(f"{L['active_account']}：{st.session_state.active_account}")
        a1, a2 = st.columns([2.4, 1])
        with a1:
            new_account = st.text_input(L["new_account"], placeholder=L["add_account_placeholder"], label_visibility="collapsed")
        with a2:
            if st.button(L["add_account"], use_container_width=True) and new_account.strip():
                if new_account.strip() not in st.session_state.accounts:
                    st.session_state.accounts[new_account.strip()] = normalize_positions(pd.DataFrame(), account=new_account.strip())
                    st.session_state.active_account = new_account.strip()

        if selected_view != L["account_all"]:
            action_col1, action_col2 = st.columns(2)
            with action_col1:
                if st.button(L["delete_account"], use_container_width=True):
                    if len(st.session_state.accounts) > 1:
                        st.session_state.accounts.pop(st.session_state.active_account, None)
                        st.session_state.active_account = next(iter(st.session_state.accounts.keys()))
            with action_col2:
                if st.button(L["use_default"], use_container_width=True):
                    st.session_state.accounts = split_accounts(normalize_positions(provider.get_default_positions()))

            with st.form("add_position_form", clear_on_submit=True):
                st.markdown(f"**{L['add_position']}**")
                fund_snapshot["add_label"] = fund_snapshot["code"] + " | " + fund_snapshot["code"].map(fund_name_lookup).fillna("")
                selected_label = st.selectbox(L["fund_selector"], fund_snapshot["add_label"].tolist())
                selected_code = selected_label.split(" | ")[0]
                selected_row = fund_snapshot[fund_snapshot["code"] == selected_code].iloc[0]
                mode = st.radio(L["input_mode"], ["simple", "pro"], horizontal=True, index=0)
                mode_label = L["input_mode_simple"] if mode == "simple" else L["input_mode_pro"]
                st.caption(mode_label)
                default_name = fund_name_lookup.get(selected_code, str(selected_row.get("name_zh", selected_code)))
                name = st.text_input(L["table_name"], value=default_name)
                if mode == "pro":
                    shares = st.number_input("持仓份额" if language == "zh" else "Shares", min_value=0.0, value=1000.0, step=100.0)
                    cost_per_share = st.number_input("成本单价" if language == "zh" else "Cost/share", min_value=0.0, value=float(selected_row["nav"]), step=0.01)
                    invested_amount, holding_profit = 0.0, 0.0
                else:
                    invested_amount = st.number_input("持有金额" if language == "zh" else "Holding amount", min_value=0.0, value=3000.0, step=100.0)
                    holding_profit = st.number_input("持有收益" if language == "zh" else "Holding profit", value=120.0, step=10.0)
                    shares, cost_per_share = 0.0, 0.0
                if st.form_submit_button(L["add_position"]):
                    new_row = pd.DataFrame(
                        [
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
                        ]
                    )
                    st.session_state.accounts[st.session_state.active_account] = pd.concat(
                        [normalize_positions(st.session_state.accounts[st.session_state.active_account]), new_row], ignore_index=True
                    )

            if st.button(L["clear_positions"], use_container_width=True):
                st.session_state.accounts[st.session_state.active_account] = normalize_positions(pd.DataFrame(), account=st.session_state.active_account)

            editable = normalize_positions(st.session_state.accounts[st.session_state.active_account], account=st.session_state.active_account)
            editable = localize_fund_name_column(editable, fund_name_lookup)
            st.caption(
                f"{L['input_fields']}：input_mode / shares / cost_per_share / invested_amount / holding_profit"
            )
            st.session_state.accounts[st.session_state.active_account] = st.data_editor(
                editable,
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                key=f"editor_{st.session_state.active_account}",
                column_config={
                    "account": st.column_config.TextColumn("Account", disabled=True),
                    "code": st.column_config.TextColumn(L["table_code"]),
                    "name": st.column_config.TextColumn(L["table_name"]),
                    "input_mode": st.column_config.SelectboxColumn(L["table_mode"], options=["simple", "pro"]),
                    "shares": st.column_config.NumberColumn(L["table_shares"], format="%.2f"),
                    "cost_per_share": st.column_config.NumberColumn(L["table_cost"], format="¥ %.4f"),
                    "invested_amount": st.column_config.NumberColumn(L["table_invest"], format="¥ %.2f"),
                    "holding_profit": st.column_config.NumberColumn(L["table_profit_input"], format="¥ %.2f"),
                },
            )
        st.markdown('</div>', unsafe_allow_html=True)

all_positions = pd.concat([normalize_positions(df, account=acc) for acc, df in st.session_state.accounts.items()], ignore_index=True)
all_positions = normalize_positions(all_positions)
all_positions = all_positions[all_positions["code"].str.strip() != ""]

if selected_view == L["account_all"]:
    current_positions = all_positions
else:
    current_positions = all_positions[all_positions["account"] == st.session_state.active_account]

position_metrics = calc_position_metrics(current_positions, fund_snapshot)
position_metrics = localize_fund_name_column(position_metrics, fund_name_lookup)
kpis = calc_portfolio_kpis(position_metrics)
account_kpis = calc_account_kpis(calc_position_metrics(all_positions, fund_snapshot))

with right_col:
    with compat_container(border=False):
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="section-title">{L["source_header"]}</div>', unsafe_allow_html=True)
        meta = provider.get_meta()
        s1, s2, s3 = st.columns(3)
        s1.metric(L["source_label"], meta.source_label_zh if language == "zh" else meta.source_label_en)
        s2.metric(L["source_mode"], meta.data_mode)
        s3.metric(L["source_time"], meta.updated_at.strftime("%Y-%m-%d %H:%M:%S"))
        official_ratio = float((fund_snapshot.get("valuation_kind", pd.Series(dtype=str)) == "official_estimate").mean() or 0.0)
        approx_ratio = kpis["approx_position_ratio"]
        s4, s5, s6 = st.columns([1.55, 1, 1])
        dom = "official_estimate" if official_ratio >= 0.5 else "approx_from_change"
        s4.markdown(f"**{L['source_valuation']}**")
        s4.caption(valuation_text(dom, language))
        s5.metric(L["source_est_coverage"], f"{official_ratio * 100:.1f}%")
        s6.metric(L["source_approx_ratio"], f"{approx_ratio * 100:.1f}%")
        st.markdown(f'<div class="footnote">{L["product_disclaimer"]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with compat_container(border=False):
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="section-title">{L["kpi_header"]}</div>', unsafe_allow_html=True)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("总成本" if language == "zh" else "Total Cost", money(kpis["total_cost"]))
        k2.metric("当前市值" if language == "zh" else "Market Value", money(kpis["total_market"]))
        k3.metric("今日预估收益" if language == "zh" else "Today Est PnL", money(kpis["today_est_profit"]))
        k4.metric("累计收益率" if language == "zh" else "Return", pct(kpis["total_return_rate"]))
        st.markdown('</div>', unsafe_allow_html=True)

    with compat_container(border=False):
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="section-title">{L["analysis_header"]}</div>', unsafe_allow_html=True)
        st.caption(f"{L['system_fields']}：nav / est_nav / today_est_profit / total_profit / profit_rate")
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
        st.dataframe(
            analysis_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "invested_amount": st.column_config.NumberColumn(L["table_invest"], format="¥ %.2f"),
                "holding_profit": st.column_config.NumberColumn(L["table_profit_input"], format="¥ %.2f"),
                "cost_per_share": st.column_config.NumberColumn(L["table_cost"], format="¥ %.4f"),
                "nav": st.column_config.NumberColumn(L["table_nav"], format="%.4f"),
                "est_nav": st.column_config.NumberColumn(L["table_est_nav"], format="%.4f"),
                "today_est_profit": st.column_config.NumberColumn(L["table_today_pnl"], format="¥ %.2f"),
                "total_profit": st.column_config.NumberColumn(L["table_total_pnl"], format="¥ %.2f"),
                "profit_rate": st.column_config.NumberColumn(L["table_return"], format="%.2f%%"),
            },
        )
        if not account_kpis.empty:
            st.markdown("**账户 KPI**" if language == "zh" else "**Account KPI**")
            account_kpis = account_kpis.sort_values("today_est_profit", ascending=False).reset_index(drop=True)
            st.dataframe(
                account_kpis,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "total_cost": st.column_config.NumberColumn("总成本" if language == "zh" else "Total cost", format="¥ %.2f"),
                    "total_market": st.column_config.NumberColumn("当前市值" if language == "zh" else "Market value", format="¥ %.2f"),
                    "today_est_profit": st.column_config.NumberColumn("今日预估收益" if language == "zh" else "Today est pnl", format="¥ %.2f"),
                    "total_return_rate": st.column_config.NumberColumn("累计收益率" if language == "zh" else "Return rate", format="%.2f%%"),
                },
            )
            fig_acc = px.bar(
                account_kpis,
                x="account",
                y="total_return_rate",
                color="today_est_profit",
                color_continuous_scale=["#ef4444", "#f59e0b", "#22c55e"],
                title="账户收益率对比" if language == "zh" else "Account return-rate comparison",
            )
            fig_acc.update_layout(template=plotly_template, height=250, coloraxis_showscale=False, margin=dict(l=8, r=8, t=40, b=6))
            fig_acc.update_layout(
                font=dict(color=plotly_font_color),
                paper_bgcolor=plotly_paper_bg,
                plot_bgcolor=plotly_paper_bg,
                xaxis=dict(gridcolor=plotly_axis_grid),
                yaxis=dict(gridcolor=plotly_axis_grid),
                hoverlabel=dict(bgcolor=plotly_hover_bg, font=dict(color=plotly_hover_font, size=12)),
            )
            st.plotly_chart(fig_acc, use_container_width=True, config=plotly_config)
        st.markdown('</div>', unsafe_allow_html=True)

    with compat_container(border=False):
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="section-title">{L["charts_header"]}</div>', unsafe_allow_html=True)
        trend_col, bar_col = st.columns(2)
        with trend_col:
            st.markdown(f"**{L['chart_nav']}**")
            labels = (fund_snapshot["code"] + " | " + fund_snapshot["code"].map(fund_name_lookup).fillna("")).tolist()
            selected_label = st.selectbox(L["chart_fund"], labels)
            chart_code = selected_label.split(" | ")[0]
            trend_df = provider.get_trend(chart_code, days=120)
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(x=trend_df["date"], y=trend_df["nav"], mode="lines", name="NAV", line=dict(color="#2563eb", width=2.6)))
            fig_trend.add_trace(
                go.Scatter(
                    x=trend_df["date"], y=trend_df["est_nav"], mode="lines", name="Est NAV", line=dict(color="#0ea5e9", dash="dot", width=2.2)
                )
            )
            fig_trend.update_layout(
                template=plotly_template,
                height=330,
                xaxis_title=L["chart_date"],
                yaxis_title=L["chart_nav_axis"],
                legend=dict(orientation="h", y=1.05, x=0),
                margin=dict(l=6, r=6, t=16, b=4),
                font=dict(color=plotly_font_color),
                paper_bgcolor=plotly_paper_bg,
                plot_bgcolor=plotly_paper_bg,
                xaxis=dict(gridcolor=plotly_axis_grid),
                yaxis=dict(gridcolor=plotly_axis_grid),
                hoverlabel=dict(bgcolor=plotly_hover_bg, font=dict(color=plotly_hover_font, size=12)),
            )
            st.plotly_chart(fig_trend, use_container_width=True, config=plotly_config)
            if not bool(trend_df.get("has_est_history", pd.Series([True])).iloc[0]):
                st.info(L["trend_degrade"])

        with bar_col:
            st.markdown(f"**{L['chart_profit']}**")
            if position_metrics.empty:
                st.warning(L["no_holdings"])
            else:
                chart_data = position_metrics.copy()
                chart_data["valuation_kind_label"] = chart_data["valuation_kind"].map(lambda x: valuation_text(x, language))
                chart_data = chart_data.sort_values("today_est_profit", ascending=False)
                fig_bar = px.bar(
                    chart_data,
                    x="name",
                    y="today_est_profit",
                    color="today_est_profit",
                    color_continuous_scale=["#ef4444", "#f59e0b", "#22c55e"],
                    hover_data=["account", "code", "valuation_kind_label", "snapshot_time"],
                )
                fig_bar.update_layout(
                    template=plotly_template,
                    height=330,
                    yaxis_title=L["chart_today_pnl"],
                    xaxis_title="",
                    margin=dict(l=6, r=6, t=14, b=20),
                    coloraxis_showscale=False,
                    xaxis=dict(tickangle=-12, tickfont=dict(size=11), gridcolor=plotly_axis_grid),
                    yaxis=dict(gridcolor=plotly_axis_grid),
                    font=dict(color=plotly_font_color),
                    paper_bgcolor=plotly_paper_bg,
                    plot_bgcolor=plotly_paper_bg,
                    hoverlabel=dict(bgcolor=plotly_hover_bg, font=dict(color=plotly_hover_font, size=12)),
                )
                st.plotly_chart(fig_bar, use_container_width=True, config=plotly_config)
        st.markdown('</div>', unsafe_allow_html=True)

    with compat_container(border=False):
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="section-title">{L["insights_header"]}</div>', unsafe_allow_html=True)
        for insight in generate_auto_insights(position_metrics, language=language):
            st.write(f"- {insight}")
        st.markdown('</div>', unsafe_allow_html=True)
