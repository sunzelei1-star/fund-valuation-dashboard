"""Portfolio analytics helpers for the dashboard."""

from __future__ import annotations

import pandas as pd


PRO_INPUT_MODE = "pro"
SIMPLE_INPUT_MODE = "simple"

REQUIRED_METRIC_COLUMNS = [
    "account",
    "code",
    "name",
    "input_mode",
    "shares",
    "cost_per_share",
    "invested_amount",
    "holding_profit",
    "nav",
    "est_nav",
    "day_change_pct",
    "valuation_kind",
    "est_nav_is_approx",
    "snapshot_time",
    "cost_value",
    "market_value",
    "est_market_value",
    "today_est_profit",
    "total_profit",
    "profit_rate",
    "is_profit",
    "today_contribution_rate",
]


def _ensure_position_schema(positions: pd.DataFrame) -> pd.DataFrame:
    wanted = [
        "account",
        "code",
        "name",
        "input_mode",
        "shares",
        "cost_per_share",
        "invested_amount",
        "holding_profit",
    ]
    df = positions.copy()
    for col in wanted:
        if col not in df.columns:
            df[col] = "" if col in {"account", "code", "name", "input_mode"} else 0.0

    df["account"] = df["account"].astype(str)
    df["code"] = df["code"].astype(str)
    df["name"] = df["name"].astype(str)
    df["input_mode"] = df["input_mode"].replace("", PRO_INPUT_MODE).fillna(PRO_INPUT_MODE)
    for num_col in ["shares", "cost_per_share", "invested_amount", "holding_profit"]:
        df[num_col] = pd.to_numeric(df[num_col], errors="coerce").fillna(0.0)

    return df[wanted]


def calc_position_metrics(positions: pd.DataFrame, snapshot_df: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        empty_df = _ensure_position_schema(positions)
        for col in REQUIRED_METRIC_COLUMNS:
            if col not in empty_df.columns:
                empty_df[col] = 0.0 if col not in {"account", "code", "name", "input_mode", "valuation_kind", "snapshot_time"} else ""
        empty_df["valuation_kind"] = empty_df["valuation_kind"].replace("", "nav_snapshot")
        empty_df["est_nav_is_approx"] = True
        empty_df = empty_df[REQUIRED_METRIC_COLUMNS]
        return empty_df

    positions = _ensure_position_schema(positions)
    snapshot_cols = snapshot_df[
        [
            col
            for col in [
                "code",
                "name_zh",
                "name_en",
                "nav",
                "est_nav",
                "day_change_pct",
                "valuation_kind",
                "est_nav_is_approx",
                "snapshot_time",
            ]
            if col in snapshot_df.columns
        ]
    ]
    merged = positions.merge(snapshot_cols, on="code", how="left")
    if "name_zh" not in merged.columns:
        merged["name_zh"] = pd.NA
    if "name_en" not in merged.columns:
        merged["name_en"] = pd.NA
    merged["name"] = merged["name"].replace("", pd.NA).fillna(merged["name_zh"]).fillna(merged["name_en"]).fillna(merged["code"])
    merged["nav"] = pd.to_numeric(merged["nav"], errors="coerce").fillna(0.0)
    merged["est_nav"] = pd.to_numeric(merged.get("est_nav", merged["nav"]), errors="coerce").fillna(merged["nav"])
    merged["day_change_pct"] = pd.to_numeric(merged.get("day_change_pct", 0.0), errors="coerce").fillna(0.0)
    merged["shares"] = pd.to_numeric(merged["shares"], errors="coerce").fillna(0.0).astype(float)
    merged["cost_per_share"] = pd.to_numeric(merged["cost_per_share"], errors="coerce").fillna(0.0).astype(float)
    merged["invested_amount"] = pd.to_numeric(merged["invested_amount"], errors="coerce").fillna(0.0).astype(float)
    merged["holding_profit"] = pd.to_numeric(merged["holding_profit"], errors="coerce").fillna(0.0).astype(float)
    if "snapshot_time" not in merged.columns:
        merged["snapshot_time"] = ""
    merged["snapshot_time"] = merged["snapshot_time"].fillna("").astype(str)
    if "valuation_kind" not in merged.columns:
        merged["valuation_kind"] = "nav_snapshot"
    merged["valuation_kind"] = merged["valuation_kind"].fillna("nav_snapshot")
    if "est_nav_is_approx" not in merged.columns:
        merged["est_nav_is_approx"] = True
    merged["est_nav_is_approx"] = merged["est_nav_is_approx"].fillna(True)

    pro_mask = merged["input_mode"].eq(PRO_INPUT_MODE)
    simple_mask = merged["input_mode"].eq(SIMPLE_INPUT_MODE)

    merged["cost_value"] = 0.0
    merged["market_value"] = 0.0
    merged.loc[pro_mask, "cost_value"] = merged.loc[pro_mask, "shares"] * merged.loc[pro_mask, "cost_per_share"]
    merged.loc[pro_mask, "market_value"] = merged.loc[pro_mask, "shares"] * merged.loc[pro_mask, "nav"]

    merged.loc[simple_mask, "market_value"] = merged.loc[simple_mask, "invested_amount"]
    merged.loc[simple_mask, "cost_value"] = merged.loc[simple_mask, "invested_amount"] - merged.loc[simple_mask, "holding_profit"]
    merged["cost_value"] = merged["cost_value"].clip(lower=0.0)

    synthetic_shares = (merged["market_value"] / merged["nav"]).replace([float("inf")], 0.0).fillna(0.0)
    merged.loc[simple_mask, "shares"] = synthetic_shares[simple_mask]
    synthetic_cost = (merged["cost_value"] / merged["shares"]).replace([float("inf")], 0.0).fillna(0.0)
    merged.loc[simple_mask, "cost_per_share"] = synthetic_cost[simple_mask]

    merged["est_market_value"] = merged["shares"] * merged["est_nav"]
    merged["today_est_profit"] = merged["est_market_value"] - merged["market_value"]
    merged["total_profit"] = merged["market_value"] - merged["cost_value"]
    merged["profit_rate"] = (merged["total_profit"] / merged["cost_value"]).replace([float("inf")], 0.0).fillna(0.0)
    merged["is_profit"] = merged["total_profit"] >= 0

    total_today = merged["today_est_profit"].sum()
    if abs(total_today) < 1e-12:
        merged["today_contribution_rate"] = 0.0
    else:
        merged["today_contribution_rate"] = merged["today_est_profit"] / total_today

    for col in REQUIRED_METRIC_COLUMNS:
        if col not in merged.columns:
            merged[col] = 0.0 if col not in {"account", "code", "name", "input_mode", "valuation_kind", "snapshot_time"} else ""

    return merged[REQUIRED_METRIC_COLUMNS]


def calc_portfolio_kpis(position_metrics: pd.DataFrame) -> dict:
    if position_metrics.empty:
        return {
            "total_cost": 0.0,
            "total_market": 0.0,
            "today_est_profit": 0.0,
            "total_profit": 0.0,
            "total_return_rate": 0.0,
            "volatility_flag": "N/A",
            "approx_position_ratio": 0.0,
        }

    total_cost = position_metrics["cost_value"].sum()
    total_market = position_metrics["market_value"].sum()
    today_est_profit = position_metrics["today_est_profit"].sum()
    total_profit = position_metrics["total_profit"].sum()
    return_rate = total_profit / total_cost if total_cost else 0.0
    approx_ratio = position_metrics["est_nav_is_approx"].mean() if "est_nav_is_approx" in position_metrics.columns else 1.0

    mean_abs_day_move = position_metrics["day_change_pct"].abs().mean()
    if mean_abs_day_move < 0.8:
        volatility_flag = "Low"
    elif mean_abs_day_move < 1.6:
        volatility_flag = "Medium"
    else:
        volatility_flag = "High"

    return {
        "total_cost": float(total_cost),
        "total_market": float(total_market),
        "today_est_profit": float(today_est_profit),
        "total_profit": float(total_profit),
        "total_return_rate": float(return_rate),
        "volatility_flag": volatility_flag,
        "approx_position_ratio": float(0.0 if pd.isna(approx_ratio) else approx_ratio),
    }


def calc_account_kpis(position_metrics: pd.DataFrame) -> pd.DataFrame:
    if position_metrics.empty:
        return pd.DataFrame(columns=["account", "total_cost", "total_market", "today_est_profit", "total_profit", "total_return_rate"])

    grouped = (
        position_metrics.groupby("account", dropna=False)
        .agg(total_cost=("cost_value", "sum"), total_market=("market_value", "sum"), today_est_profit=("today_est_profit", "sum"), total_profit=("total_profit", "sum"))
        .reset_index()
    )
    grouped["total_return_rate"] = (grouped["total_profit"] / grouped["total_cost"]).replace([float("inf")], 0.0).fillna(0.0)
    return grouped


def generate_auto_insights(position_metrics: pd.DataFrame, language: str = "zh") -> list[str]:
    if position_metrics.empty:
        return [
            "请先录入持仓，系统将自动给出收益和风险结论。"
            if language == "zh"
            else "Add your holdings first to unlock automated performance and risk insights."
        ]

    winner = position_metrics.loc[position_metrics["today_est_profit"].idxmax()]
    loser = position_metrics.loc[position_metrics["today_est_profit"].idxmin()]
    kpis = calc_portfolio_kpis(position_metrics)
    by_account = calc_account_kpis(position_metrics)
    max_contrib = by_account.loc[by_account["today_est_profit"].idxmax()] if not by_account.empty else None
    top_rr = by_account.loc[by_account["total_return_rate"].idxmax()] if not by_account.empty else None
    low_rr = by_account.loc[by_account["total_return_rate"].idxmin()] if not by_account.empty else None

    if language == "zh":
        insights = [
            f"今日贡献最大基金：{winner['name']}，预估贡献 {winner['today_est_profit']:.2f} 元。",
            f"今日拖累最大基金：{loser['name']}，预估影响 {loser['today_est_profit']:.2f} 元。",
            f"组合波动等级：{kpis['volatility_flag']}（基于持仓基金当日涨跌幅绝对值均值）。",
            f"近似估值仓位占比：{kpis['approx_position_ratio'] * 100:.1f}%。",
        ]
        if max_contrib is not None:
            insights.append(f"账户贡献最大：{max_contrib['account']}，今日预估贡献 {max_contrib['today_est_profit']:.2f} 元。")
        if top_rr is not None and low_rr is not None:
            insights.append(
                f"账户收益率最高/最低：{top_rr['account']}({top_rr['total_return_rate']:.2%}) / {low_rr['account']}({low_rr['total_return_rate']:.2%})。"
            )
        insights.append("风险提示：估值并非最终净值，短期波动不代表长期趋势，请结合仓位控制。")
        return insights

    insights = [
        f"Top fund contributor today: {winner['name']} ({winner['today_est_profit']:.2f}).",
        f"Largest fund drag today: {loser['name']} ({loser['today_est_profit']:.2f}).",
        f"Portfolio volatility level: {kpis['volatility_flag']} (from average absolute day change).",
        f"Approximate-valuation position ratio: {kpis['approx_position_ratio'] * 100:.1f}%.",
    ]
    if max_contrib is not None:
        insights.append(f"Largest account contributor: {max_contrib['account']} ({max_contrib['today_est_profit']:.2f}).")
    if top_rr is not None and low_rr is not None:
        insights.append(
            f"Best/Worst account return: {top_rr['account']}({top_rr['total_return_rate']:.2%}) / {low_rr['account']}({low_rr['total_return_rate']:.2%})."
        )
    insights.append("Risk note: estimated NAV is not final NAV; avoid overreacting to one-day moves.")
    return insights
