from __future__ import annotations

from datetime import datetime, timezone
import logging
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
        self._snapshot_data_updated_at: datetime | None = None
        self._last_snapshot_columns: list[str] = []
        self._lock = threading.RLock()
        self._trend_fallback_provider = LocalMockFundProvider()
        self._logger = logging.getLogger(self.__class__.__name__)

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

    @staticmethod
    def _norm_col(col: str) -> str:
        return str(col).strip().lower().replace(" ", "").replace("_", "")

    def _find_column(self, columns: list[str], aliases: list[str]) -> str | None:
        norm_map = {self._norm_col(col): col for col in columns}
        for alias in aliases:
            alias_norm = self._norm_col(alias)
            if alias_norm in norm_map:
                return norm_map[alias_norm]
        for alias in aliases:
            alias_norm = self._norm_col(alias)
            for norm_col, original in norm_map.items():
                if alias_norm in norm_col:
                    return original
        return None

    def _parse_updated_at(self, raw_df: pd.DataFrame, columns: list[str]) -> datetime | None:
        date_col = self._find_column(columns, ["净值日期", "日期", "更新时间", "update_time", "time"])
        if date_col is None:
            return None
        parsed = pd.to_datetime(raw_df[date_col], errors="coerce", utc=True)
        valid = parsed.dropna()
        if valid.empty:
            return None
        return valid.max().to_pydatetime()

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
        if raw_df is None or not isinstance(raw_df, pd.DataFrame):
            raise RuntimeError("AKShare 快照接口返回非表格结构，可能是限流或接口异常。")
        if raw_df.empty:
            raise RuntimeError("AKShare 快照接口返回空表，可能是网络异常、限流或数据源暂不可用。")

        columns = [str(c) for c in raw_df.columns]
        self._last_snapshot_columns = columns
        self._logger.info("AKShare fund_open_fund_daily_em columns: %s", columns)

        code_col = self._find_column(columns, ["基金代码", "代码", "基金code", "fund_code", "code"])
        name_col = self._find_column(columns, ["基金简称", "基金名称", "名称", "fund_name", "name"])
        nav_col = self._find_column(columns, ["单位净值", "最新净值", "净值", "nav", "单位净值(元)"])
        day_change_col = self._find_column(columns, ["日增长率", "日涨跌幅", "涨跌幅", "日增长", "daily_change_pct"])
        est_nav_col = self._find_column(columns, ["估算净值", "最新估值", "估值", "est_nav", "estimated_nav"])

        if code_col is None or nav_col is None:
            raise RuntimeError(
                "AKShare 快照关键字段缺失（至少需要 code/nav）。"
                f" 实际返回列: {columns}"
            )

        snap = pd.DataFrame(
            {
                "code": raw_df[code_col].map(self._normalize_code),
                "nav": pd.to_numeric(raw_df[nav_col], errors="coerce"),
            }
        )
        if name_col is not None:
            snap["name_zh_from_snapshot"] = raw_df[name_col].astype(str).str.strip()

        if day_change_col is not None:
            snap["day_change_pct"] = pd.to_numeric(raw_df[day_change_col], errors="coerce")
        else:
            snap["day_change_pct"] = 0.0

        if est_nav_col is not None:
            snap["est_nav"] = pd.to_numeric(raw_df[est_nav_col], errors="coerce")
        else:
            snap["est_nav"] = snap["nav"]

        snap["day_change_pct"] = snap["day_change_pct"].fillna(0.0)
        snap["est_nav"] = snap["est_nav"].fillna(snap["nav"])
        snap = snap.dropna(subset=["nav"])
        snap["nav"] = snap["nav"].round(4)
        snap["est_nav"] = snap["est_nav"].round(4)
        snap = snap.drop_duplicates(subset=["code"], keep="first")
        snap = snap[snap["code"].str.fullmatch(r"\d{6}", na=False)]
        if snap.empty:
            raise RuntimeError(
                "AKShare 快照解析后为空，可能是字段结构变化或返回了异常页面。"
                f" 实际返回列: {columns}"
            )

        updated_at = self._parse_updated_at(raw_df, columns)
        if updated_at is not None:
            self._snapshot_data_updated_at = updated_at

        merged = catalog_df.merge(snap, on="code", how="inner")
        if "name_zh_from_snapshot" in merged.columns:
            merged["name_zh"] = merged["name_zh"].fillna("").where(
                merged["name_zh"].fillna("") != "",
                merged["name_zh_from_snapshot"],
            )
            merged["name_en"] = merged["name_zh"]

        if merged.empty:
            raise RuntimeError(
                "AKShare 快照与基金主数据 merge 后为空，可能是代码格式或接口字段变更。"
                f" 实际返回列: {columns}"
            )

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
        updated_at = self._snapshot_data_updated_at or self._last_success_at or self._now_utc()
        notes_zh = "AKShare 开放式基金日净值快照（盘后更新）；展示为净值级快照，不是逐笔实时成交价。"
        notes_en = (
            "AKShare open-fund daily NAV snapshot (typically post-close updates); "
            "shown as NAV-level snapshot, not tick-by-tick real-time trade prices."
        )
        if self._last_snapshot_columns:
            notes_zh += f" 最近一次快照列: {self._last_snapshot_columns[:12]}"
            notes_en += f" Last snapshot columns: {self._last_snapshot_columns[:12]}"
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
