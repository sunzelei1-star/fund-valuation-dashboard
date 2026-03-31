"""Mock data provider for fund dashboard MVP.

This module intentionally keeps data deterministic and replaceable so the
project can switch to real APIs later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
from typing import Dict, List

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FundSnapshot:
    code: str
    name_zh: str
    name_en: str
    nav: float
    est_nav: float
    day_change_pct: float

    @property
    def est_profit_per_unit(self) -> float:
        return self.est_nav - self.nav


FUND_CATALOG: List[Dict[str, str]] = [
    {"code": "161725", "name_zh": "招商中证白酒指数", "name_en": "CMF CSI Liquor Index"},
    {"code": "110022", "name_zh": "易方达消费行业", "name_en": "E Fund Consumer Sector"},
    {"code": "260108", "name_zh": "景顺长城新兴成长", "name_en": "Invesco Great Wall Emerging Growth"},
    {"code": "005827", "name_zh": "易方达蓝筹精选", "name_en": "E Fund Blue Chip Select"},
    {"code": "001632", "name_zh": "天弘中证食品饮料ETF联接", "name_en": "Tianhong Food & Beverage ETF Link"},
    {"code": "000248", "name_zh": "汇添富中证主要消费ETF联接", "name_en": "China Universal Consumer ETF Link"},
    {"code": "004224", "name_zh": "南方军工改革灵活配置", "name_en": "CSOP Defense Reform Allocation"},
    {"code": "003095", "name_zh": "中欧医疗健康混合", "name_en": "Zhongou Healthcare Mix"},
]


def _stable_random_from_code(code: str) -> np.random.Generator:
    seed = int(hashlib.md5(code.encode("utf-8")).hexdigest()[:8], 16)
    return np.random.default_rng(seed)


def _generate_snapshot(code: str, name_zh: str, name_en: str) -> FundSnapshot:
    rng = _stable_random_from_code(code)
    nav = float(np.round(rng.uniform(0.8, 4.2), 4))
    day_change_pct = float(np.round(rng.normal(loc=0.12, scale=1.35), 2))
    est_nav = float(np.round(nav * (1 + day_change_pct / 100), 4))
    return FundSnapshot(
        code=code,
        name_zh=name_zh,
        name_en=name_en,
        nav=nav,
        est_nav=est_nav,
        day_change_pct=day_change_pct,
    )


def get_fund_snapshots() -> pd.DataFrame:
    snapshots = [_generate_snapshot(**fund) for fund in FUND_CATALOG]
    return pd.DataFrame([snapshot.__dict__ for snapshot in snapshots])


def search_fund(keyword: str) -> pd.DataFrame:
    if not keyword.strip():
        return get_fund_snapshots()

    df = get_fund_snapshots()
    key = keyword.strip().lower()
    mask = (
        df["code"].str.lower().str.contains(key)
        | df["name_zh"].str.lower().str.contains(key)
        | df["name_en"].str.lower().str.contains(key)
    )
    return df[mask].reset_index(drop=True)


def get_mock_trend(code: str, days: int = 60) -> pd.DataFrame:
    rng = _stable_random_from_code(code)
    end = date.today()
    dates = [end - timedelta(days=i) for i in range(days)][::-1]

    base = rng.uniform(0.9, 3.5)
    daily_returns = rng.normal(0.0008, 0.012, size=days)
    nav_series = np.array([base])
    for r in daily_returns[1:]:
        nav_series = np.append(nav_series, nav_series[-1] * (1 + r))

    premium = rng.normal(0.0, 0.004, size=days)
    est_series = nav_series * (1 + premium)

    return pd.DataFrame(
        {
            "date": dates,
            "nav": np.round(nav_series, 4),
            "est_nav": np.round(est_series, 4),
        }
    )


def get_default_positions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"code": "161725", "name": "招商中证白酒指数", "shares": 2200.0, "cost_per_share": 1.12},
            {"code": "110022", "name": "易方达消费行业", "shares": 1800.0, "cost_per_share": 1.56},
            {"code": "003095", "name": "中欧医疗健康混合", "shares": 900.0, "cost_per_share": 2.34},
        ]
    )
