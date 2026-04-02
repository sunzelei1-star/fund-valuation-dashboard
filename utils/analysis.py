"""Portfolio analytics helpers for the dashboard."""

from __future__ import annotations

import pandas as pd


def calc_position_metrics(positions: pd.DataFrame, snapshot_df: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        return positions

    snapshot_cols = snapshot_df[
        [col for col in ["code", "name_zh", "name_en", "nav", "est_nav", "day_change_pct", "valuation_kind", "est_nav_is_approx"] if col in snapshot_df.columns]
    ]
    merged = positions.merge(snapshot_cols, on="code", how="left")
    merged["name"] = merged["name"].fillna(merged["name_zh"]).fillna(merged["name_en"]).fillna(merged["code"])
    merged["nav"] = pd.to_numeric(merged["nav"], errors="coerce").fillna(0.0)
    merged["est_nav"] = pd.to_numeric(merged.get("est_nav", merged["nav"]), errors="coerce").fillna(merged["nav"])
    merged["day_change_pct"] = pd.to_numeric(merged.get("day_change_pct", 0.0), errors="coerce").fillna(0.0)
    if "valuation_kind" not in merged.columns:
        merged["valuation_kind"] = "nav_snapshot"
    if "est_nav_is_approx" not in merged.columns:
        merged["est_nav_is_approx"] = True

    merged["cost_value"] = merged["shares"] * merged["cost_per_share"]
    merged["market_value"] = merged["shares"] * merged["nav"]
    merged["est_market_value"] = merged["shares"] * merged["est_nav"]

    merged["today_est_profit"] = merged["est_market_value"] - merged["market_value"]
    merged["total_profit"] = merged["market_value"] - merged["cost_value"]
    merged["profit_rate"] = (merged["total_profit"] / merged["cost_value"]).replace([float("inf")], 0.0)

    return merged


def calc_portfolio_kpis(position_metrics: pd.DataFrame) -> dict:
    if position_metrics.empty:
        return {
            "total_cost": 0.0,
            "total_market": 0.0,
            "today_est_profit": 0.0,
            "total_profit": 0.0,
            "total_return_rate": 0.0,
            "volatility_flag": "N/A",
        }

    total_cost = position_metrics["cost_value"].sum()
    total_market = position_metrics["market_value"].sum()
    today_est_profit = position_metrics["today_est_profit"].sum()
    total_profit = position_metrics["total_profit"].sum()
    return_rate = total_profit / total_cost if total_cost else 0.0

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
    }


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

    if language == "zh":
        return [
            f"今日贡献最大：{winner['name']}，预估贡献 {winner['today_est_profit']:.2f} 元。",
            f"今日拖累最大：{loser['name']}，预估影响 {loser['today_est_profit']:.2f} 元。",
            f"组合波动等级：{kpis['volatility_flag']}（基于持仓基金当日涨跌幅绝对值均值）。",
            "风险提示：估值并非最终净值，短期波动不代表长期趋势，请结合仓位控制。",
        ]

    return [
        f"Top contributor today: {winner['name']} with an estimated gain of {winner['today_est_profit']:.2f}.",
        f"Largest drag today: {loser['name']} with an estimated impact of {loser['today_est_profit']:.2f}.",
        f"Portfolio volatility level: {kpis['volatility_flag']} (based on average absolute daily changes).",
        "Risk note: estimated NAV is not final NAV; avoid overreacting to one-day moves.",
    ]
