"""Deterministic local provider for portfolio demo and architecture extension."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import hashlib
from typing import Dict, List

import numpy as np
import pandas as pd

from data.providers.base import ProviderMeta


@dataclass(frozen=True)
class FundSnapshot:
    code: str
    name_zh: str
    name_en: str
    category: str
    nav: float
    est_nav: float
    day_change_pct: float


FUND_CATALOG: List[Dict[str, str]] = [
    {"code": "161725", "name_zh": "招商中证白酒指数", "name_en": "CMF CSI Liquor Index", "category": "Consumer"},
    {"code": "110022", "name_zh": "易方达消费行业", "name_en": "E Fund Consumer Sector", "category": "Consumer"},
    {"code": "260108", "name_zh": "景顺长城新兴成长", "name_en": "Invesco Great Wall Emerging Growth", "category": "Growth"},
    {"code": "005827", "name_zh": "易方达蓝筹精选", "name_en": "E Fund Blue Chip Select", "category": "Equity"},
    {"code": "001632", "name_zh": "天弘中证食品饮料ETF联接", "name_en": "Tianhong Food & Beverage ETF Link", "category": "Consumer"},
    {"code": "000248", "name_zh": "汇添富中证主要消费ETF联接", "name_en": "China Universal Consumer ETF Link", "category": "Consumer"},
    {"code": "004224", "name_zh": "南方军工改革灵活配置", "name_en": "CSOP Defense Reform Allocation", "category": "Defense"},
    {"code": "003095", "name_zh": "中欧医疗健康混合", "name_en": "Zhongou Healthcare Mix", "category": "Healthcare"},
    {"code": "012348", "name_zh": "广发中证新能源车", "name_en": "GF New Energy Vehicle Index", "category": "New Energy"},
    {"code": "006113", "name_zh": "华夏中证5G通信主题ETF联接", "name_en": "ChinaAMC 5G Theme ETF Link", "category": "Tech"},
    {"code": "001938", "name_zh": "中欧时代先锋股票", "name_en": "Zhongou Era Pioneer Equity", "category": "Equity"},
    {"code": "320007", "name_zh": "诺安成长混合", "name_en": "Nuode Growth Mix", "category": "Tech"},
    {"code": "000961", "name_zh": "天弘沪深300指数", "name_en": "Tianhong CSI 300 Index", "category": "Broad Market"},
    {"code": "161039", "name_zh": "富国中证1000指数增强", "name_en": "Fullgoal CSI 1000 Enhanced", "category": "Broad Market"},
    {"code": "007119", "name_zh": "睿远成长价值混合", "name_en": "Ruiyuan Growth Value Mix", "category": "Value"},
    {"code": "005918", "name_zh": "工银前沿医疗股票", "name_en": "ICBC Frontier Healthcare Equity", "category": "Healthcare"},
    {"code": "002190", "name_zh": "农银新能源主题", "name_en": "ABC New Energy Theme", "category": "New Energy"},
    {"code": "005911", "name_zh": "广发双擎升级混合", "name_en": "GF Dual Engine Upgrade Mix", "category": "Growth"},
    {"code": "008282", "name_zh": "兴全合润混合", "name_en": "Xingquan Herun Mix", "category": "Balanced"},
    {"code": "501018", "name_zh": "南方原油LOF", "name_en": "CSOP Crude Oil LOF", "category": "QDII"},
]


class LocalMockFundProvider:
    def _stable_random_from_code(self, code: str) -> np.random.Generator:
        seed = int(hashlib.md5(code.encode("utf-8")).hexdigest()[:8], 16)
        return np.random.default_rng(seed)

    def _generate_snapshot(self, code: str, name_zh: str, name_en: str, category: str) -> FundSnapshot:
        rng = self._stable_random_from_code(code)
        nav = float(np.round(rng.uniform(0.8, 4.2), 4))
        day_change_pct = float(np.round(rng.normal(loc=0.1, scale=1.25), 2))
        est_nav = float(np.round(nav * (1 + day_change_pct / 100), 4))
        return FundSnapshot(
            code=code,
            name_zh=name_zh,
            name_en=name_en,
            category=category,
            nav=nav,
            est_nav=est_nav,
            day_change_pct=day_change_pct,
        )

    def get_catalog(self) -> pd.DataFrame:
        return pd.DataFrame(FUND_CATALOG)

    def get_snapshots(self) -> pd.DataFrame:
        snapshots = [self._generate_snapshot(**fund) for fund in FUND_CATALOG]
        return pd.DataFrame([snapshot.__dict__ for snapshot in snapshots])

    def search(self, keyword: str) -> pd.DataFrame:
        data = self.get_snapshots()
        if not keyword.strip():
            return data
        key = keyword.strip().lower()
        mask = (
            data["code"].str.lower().str.contains(key)
            | data["name_zh"].str.lower().str.contains(key)
            | data["name_en"].str.lower().str.contains(key)
            | data["category"].str.lower().str.contains(key)
        )
        return data[mask].reset_index(drop=True)

    def get_trend(self, code: str, days: int = 90) -> pd.DataFrame:
        rng = self._stable_random_from_code(code)
        end = date.today()
        dates = [end - timedelta(days=i) for i in range(days)][::-1]
        base = rng.uniform(0.9, 3.5)
        daily_returns = rng.normal(0.0006, 0.0105, size=days)
        nav_series = np.array([base])
        for daily in daily_returns[1:]:
            nav_series = np.append(nav_series, nav_series[-1] * (1 + daily))
        premium = rng.normal(0.0, 0.0038, size=days)
        est_series = nav_series * (1 + premium)
        return pd.DataFrame({"date": dates, "nav": np.round(nav_series, 4), "est_nav": np.round(est_series, 4)})

    def get_default_positions(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"code": "161725", "name": "招商中证白酒指数", "shares": 2200.0, "cost_per_share": 1.12},
                {"code": "110022", "name": "易方达消费行业", "shares": 1800.0, "cost_per_share": 1.56},
                {"code": "003095", "name": "中欧医疗健康混合", "shares": 900.0, "cost_per_share": 2.34},
                {"code": "006113", "name": "华夏中证5G通信主题ETF联接", "shares": 1200.0, "cost_per_share": 1.42},
            ]
        )

    def get_meta(self) -> ProviderMeta:
        return ProviderMeta(
            provider_name="LocalMockFundProvider",
            source_label_zh="本地示例基金库（可替换 Provider）",
            source_label_en="Local sample fund catalog (replaceable provider)",
            data_mode="mock",
            updated_at=datetime.now(timezone.utc),
            notes_zh="当前净值/估值/趋势为确定性 mock 数据，用于演示架构与交互。",
            notes_en="Current NAV/estimated NAV/trends are deterministic mock data for demo architecture and UX.",
        )
