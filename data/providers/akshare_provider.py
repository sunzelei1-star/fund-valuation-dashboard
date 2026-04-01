from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any

import pandas as pd

from data.providers.base import ProviderMeta
from data.providers.mock_provider import LocalMockFundProvider

try:
    import akshare as ak
except Exception:  # noqa: BLE001
    ak = None


class AKShareFundProvider:
    """AKShare-backed provider for fund catalog + daily open-fund snapshots."""

    CATALOG_TTL_SECONDS = 60 * 60 * 6
    SNAPSHOT_TTL_SECONDS = 60 * 5

    def __init__(self) -> None:
        self._catalog_cache: pd.DataFrame | None = None
        self._catalog_cached_at: datetime | None = None
        self._snapshot_cache: pd.DataFrame | None = None
        self._snapshot_cached_at: datetime | None = None
        self._last_success_at: datetime | None = None
        self._last_error: str | None = None
        self._lock = threading.RLock()
        self._trend_fallback_provider = LocalMockFundProvider()

    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_code(code: Any) -> str:
        text = str(code).strip()
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            return text
        return digits.zfill(6)

    def _cache_valid(self, cached_at: datetime | None, ttl_seconds: int) -> bool:
        if cached_at is None:
            return False
        age = (self._now_utc() - cached_at).total_seconds()
        return age < ttl_seconds

    def _fetch_catalog_from_akshare(self) -> pd.DataFrame:
        if ak is None:
            raise RuntimeError("未安装或无法导入 akshare，请先执行 pip install -r requirements.txt。")
        raw_df = ak.fund_name_em()
        code_col = "基金代码" if "基金代码" in raw_df.columns else raw_df.columns[0]
        name_col = "基金简称" if "基金简称" in raw_df.columns else raw_df.columns[1]

        catalog = pd.DataFrame(
            {
                "code": raw_df[code_col].map(self._normalize_code),
                "name_zh": raw_df[name_col].astype(str).str.strip(),
            }
        )
        catalog = catalog[catalog["code"].str.fullmatch(r"\d{6}", na=False)]
        catalog = catalog[catalog["name_zh"] != ""]
        catalog = catalog.drop_duplicates(subset=["code"], keep="first").reset_index(drop=True)
        catalog["name_en"] = catalog["name_zh"]
        catalog["category"] = "Open Fund"
        return catalog

    def _fetch_snapshots_from_akshare(self, catalog_df: pd.DataFrame) -> pd.DataFrame:
        if ak is None:
            raise RuntimeError("未安装或无法导入 akshare，请先执行 pip install -r requirements.txt。")
        raw_df = ak.fund_open_fund_daily_em()

        code_col = "基金代码" if "基金代码" in raw_df.columns else raw_df.columns[0]
        nav_col = "单位净值" if "单位净值" in raw_df.columns else None
        est_nav_col = "日增长率" if "日增长率" in raw_df.columns else None

        if nav_col is None or est_nav_col is None:
            raise RuntimeError("AKShare 开放式基金快照字段缺失，无法解析单位净值或日增长率。")

        snap = pd.DataFrame(
            {
                "code": raw_df[code_col].map(self._normalize_code),
                "nav": pd.to_numeric(raw_df[nav_col], errors="coerce"),
                "day_change_pct": pd.to_numeric(raw_df[est_nav_col], errors="coerce"),
            }
        )
        snap = snap.dropna(subset=["nav", "day_change_pct"])
        snap["est_nav"] = (snap["nav"] * (1 + snap["day_change_pct"] / 100)).round(4)
        snap = snap.drop_duplicates(subset=["code"], keep="first")

        merged = catalog_df.merge(snap, on="code", how="inner")
        return merged[["code", "name_zh", "name_en", "category", "nav", "est_nav", "day_change_pct"]]

    def get_catalog(self) -> pd.DataFrame:
        with self._lock:
            if self._catalog_cache is not None and self._cache_valid(self._catalog_cached_at, self.CATALOG_TTL_SECONDS):
                return self._catalog_cache.copy()

            try:
                catalog = self._fetch_catalog_from_akshare()
                self._catalog_cache = catalog
                self._catalog_cached_at = self._now_utc()
                self._last_success_at = self._catalog_cached_at
                self._last_error = None
                return catalog.copy()
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"AKShare 基金主数据加载失败: {exc}"
                if self._catalog_cache is not None:
                    return self._catalog_cache.copy()
                raise RuntimeError(self._last_error) from exc

    def get_snapshots(self) -> pd.DataFrame:
        with self._lock:
            if self._snapshot_cache is not None and self._cache_valid(self._snapshot_cached_at, self.SNAPSHOT_TTL_SECONDS):
                return self._snapshot_cache.copy()

            catalog = self.get_catalog()
            try:
                snapshots = self._fetch_snapshots_from_akshare(catalog)
                self._snapshot_cache = snapshots
                self._snapshot_cached_at = self._now_utc()
                self._last_success_at = self._snapshot_cached_at
                self._last_error = None
                return snapshots.copy()
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"AKShare 开放式基金快照加载失败: {exc}"
                if self._snapshot_cache is not None:
                    return self._snapshot_cache.copy()
                raise RuntimeError(self._last_error) from exc

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
        normalized_code = self._normalize_code(code)
        return self._trend_fallback_provider.get_trend(normalized_code, days=days)

    def get_default_positions(self) -> pd.DataFrame:
        snapshots = self.get_snapshots()
        picks = snapshots.head(4)
        if picks.empty:
            return self._trend_fallback_provider.get_default_positions()

        positions = picks[["code", "name_zh"]].copy()
        positions = positions.rename(columns={"name_zh": "name"})
        positions["shares"] = [1000.0, 1200.0, 800.0, 1500.0][: len(positions)]
        positions["cost_per_share"] = 1.0
        return positions[["code", "name", "shares", "cost_per_share"]]

    def get_meta(self) -> ProviderMeta:
        updated_at = self._last_success_at or self._now_utc()
        notes_zh = "AKShare 开放式基金日净值快照（盘后更新）；展示为净值级快照，不是逐笔实时成交价。"
        notes_en = (
            "AKShare open-fund daily NAV snapshot (typically post-close updates); "
            "shown as NAV-level snapshot, not tick-by-tick real-time trade prices."
        )
        if self._last_error:
            notes_zh += f" 最近一次请求异常：{self._last_error}"
            notes_en += f" Last request error: {self._last_error}"

        return ProviderMeta(
            provider_name="AKShareFundProvider",
            source_label_zh="AKShare 开放式基金日净值快照",
            source_label_en="AKShare Open-Fund Daily NAV Snapshot",
            data_mode="live",
            updated_at=updated_at,
            notes_zh=notes_zh,
            notes_en=notes_en,
        )
