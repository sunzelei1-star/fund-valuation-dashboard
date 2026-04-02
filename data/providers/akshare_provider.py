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
    SNAPSHOT_CODE_ALIASES = ("基金代码", "代码", "基金编码")
    SNAPSHOT_NAV_ALIASES = ("单位净值", "最新净值", "净值")
    SNAPSHOT_EST_NAV_ALIASES = ("估算净值", "估值", "实时估值")
    SNAPSHOT_DAY_CHANGE_ALIASES = ("日增长率", "日涨幅", "涨跌幅")
    SNAPSHOT_TIME_ALIASES = ("净值日期", "日期", "更新时间")

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

        code_col = self._pick_column(raw_df, self.SNAPSHOT_CODE_ALIASES)
        nav_col = self._pick_column(raw_df, self.SNAPSHOT_NAV_ALIASES)
        est_nav_col = self._pick_column(raw_df, self.SNAPSHOT_EST_NAV_ALIASES)
        day_change_col = self._pick_column(raw_df, self.SNAPSHOT_DAY_CHANGE_ALIASES)
        snapshot_time_col = self._pick_column(raw_df, self.SNAPSHOT_TIME_ALIASES)

        if code_col is None:
            code_col = raw_df.columns[0]
        if nav_col is None:
            raise RuntimeError("AKShare 开放式基金快照字段缺失，无法解析单位净值。")

        est_nav_raw = pd.to_numeric(raw_df[est_nav_col], errors="coerce") if est_nav_col else pd.Series(pd.NA, index=raw_df.index)
        day_change_pct = pd.to_numeric(raw_df[day_change_col], errors="coerce") if day_change_col else pd.Series(pd.NA, index=raw_df.index)
        snap = pd.DataFrame({"code": raw_df[code_col].map(self._normalize_code), "nav": pd.to_numeric(raw_df[nav_col], errors="coerce")})
        snap["day_change_pct"] = day_change_pct
        snap["est_nav_official"] = est_nav_raw
        snap["snapshot_time"] = raw_df[snapshot_time_col].astype(str) if snapshot_time_col else ""

        change_based_est = (snap["nav"] * (1 + snap["day_change_pct"] / 100)).round(4)
        snap["est_nav"] = snap["est_nav_official"].fillna(change_based_est).fillna(snap["nav"])
        snap["valuation_kind"] = "nav_snapshot"
        snap.loc[snap["est_nav_official"].notna(), "valuation_kind"] = "official_estimate"
        snap.loc[snap["est_nav_official"].isna() & snap["day_change_pct"].notna(), "valuation_kind"] = "approx_from_change"
        snap["est_nav_is_approx"] = snap["valuation_kind"] != "official_estimate"
        snap["day_change_pct"] = snap["day_change_pct"].fillna(0.0)
        snap = snap.dropna(subset=["nav", "est_nav"])
        snap = snap.drop_duplicates(subset=["code"], keep="first")

        merged = catalog_df.merge(snap, on="code", how="inner")
        return merged[
            [
                "code",
                "name_zh",
                "name_en",
                "category",
                "nav",
                "est_nav",
                "day_change_pct",
                "valuation_kind",
                "est_nav_is_approx",
                "snapshot_time",
            ]
        ]

    def _fetch_nav_trend(self, code: str) -> pd.DataFrame:
        if ak is None:
            raise RuntimeError("akshare unavailable")
        raw_df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        date_col = self._pick_column(raw_df, ("净值日期", "日期", "x", "date")) or raw_df.columns[0]
        nav_col = self._pick_column(raw_df, ("单位净值", "净值", "y", "value")) or raw_df.columns[-1]
        trend = pd.DataFrame({"date": pd.to_datetime(raw_df[date_col], errors="coerce"), "nav": pd.to_numeric(raw_df[nav_col], errors="coerce")})
        trend = trend.dropna(subset=["date", "nav"]).sort_values("date").drop_duplicates(subset=["date"], keep="last")
        return trend

    def _fetch_est_trend_optional(self, code: str) -> pd.DataFrame | None:
        if ak is None:
            return None
        # Different AKShare versions expose different APIs; treat estimate history as optional.
        candidates = [
            ("fund_value_estimation_em", {"symbol": code}),
            ("fund_value_estimation_em", {}),
            ("fund_estimation_em", {"symbol": code}),
        ]
        for fn_name, kwargs in candidates:
            fn = getattr(ak, fn_name, None)
            if fn is None:
                continue
            try:
                raw_df = fn(**kwargs)
                if raw_df is None or raw_df.empty:
                    continue
                code_col = self._pick_column(raw_df, ("基金代码", "代码", "symbol"))
                if code_col is not None:
                    raw_df = raw_df[raw_df[code_col].astype(str).str.contains(code)]
                date_col = self._pick_column(raw_df, ("净值日期", "日期", "更新时间", "date", "x"))
                est_col = self._pick_column(raw_df, ("估算净值", "估值", "最新估值", "y", "value"))
                if date_col is None or est_col is None:
                    continue
                est_df = pd.DataFrame(
                    {
                        "date": pd.to_datetime(raw_df[date_col], errors="coerce"),
                        "est_nav": pd.to_numeric(raw_df[est_col], errors="coerce"),
                    }
                )
                est_df = est_df.dropna(subset=["date", "est_nav"]).sort_values("date").drop_duplicates(subset=["date"], keep="last")
                if not est_df.empty:
                    return est_df
            except Exception:
                continue
        return None

    @staticmethod
    def _pick_column(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
        for alias in aliases:
            if alias in df.columns:
                return alias
        lowered = {str(col).strip().lower(): col for col in df.columns}
        for alias in aliases:
            key = alias.strip().lower()
            if key in lowered:
                return lowered[key]
        for col in df.columns:
            text = str(col)
            if any(alias in text for alias in aliases):
                return col
        return None

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
        try:
            nav_df = self._fetch_nav_trend(normalized_code)
            est_df = self._fetch_est_trend_optional(normalized_code)
            trend = nav_df.copy()
            has_est_history = est_df is not None and not est_df.empty
            if has_est_history:
                trend = trend.merge(est_df, on="date", how="left")
            trend["est_nav"] = pd.to_numeric(trend.get("est_nav", trend["nav"]), errors="coerce")
            trend["est_nav"] = trend["est_nav"].fillna(trend["nav"])
            trend["date"] = pd.to_datetime(trend["date"]).dt.date
            trend["has_est_history"] = has_est_history
            trend["trend_source"] = "akshare"
            trend = trend.sort_values("date").tail(days).reset_index(drop=True)
            return trend[["date", "nav", "est_nav", "has_est_history", "trend_source"]]
        except Exception:
            fallback = self._trend_fallback_provider.get_trend(normalized_code, days=days).copy()
            fallback["has_est_history"] = True
            fallback["trend_source"] = "fallback_mock"
            return fallback[["date", "nav", "est_nav", "has_est_history", "trend_source"]]

    def get_default_positions(self) -> pd.DataFrame:
        snapshots = self.get_snapshots()
        picks = snapshots.head(4)
        if picks.empty:
            return self._trend_fallback_provider.get_default_positions()

        positions = picks[["code", "name_zh"]].copy()
        positions = positions.rename(columns={"name_zh": "name"})
        positions["account"] = ["主账户", "支付宝", "主账户", "家庭账户"][: len(positions)]
        positions["input_mode"] = ["pro", "pro", "simple", "simple"][: len(positions)]
        positions["shares"] = [1000.0, 1200.0, 0.0, 0.0][: len(positions)]
        positions["cost_per_share"] = [1.0, 1.05, 0.0, 0.0][: len(positions)]
        positions["invested_amount"] = [0.0, 0.0, 5000.0, 3600.0][: len(positions)]
        positions["holding_profit"] = [0.0, 0.0, 420.0, -180.0][: len(positions)]
        return positions[["account", "code", "name", "input_mode", "shares", "cost_per_share", "invested_amount", "holding_profit"]]

    def get_meta(self) -> ProviderMeta:
        updated_at = self._last_success_at or self._now_utc()
        notes_zh = (
            "AKShare 开放式基金净值快照（通常盘后更新）+ 基金单位净值历史走势。"
            "若接口包含估算净值字段则标记为 official_estimate；否则尝试根据涨跌幅近似（approx_from_change）"
            "，仍不可得时降级为 nav_snapshot。"
        )
        notes_en = (
            "AKShare open-fund NAV snapshot (typically post-close) + real historical NAV trend. "
            "If estimated NAV is available, kind=official_estimate; otherwise approx_from_change from day change, "
            "and fallback to nav_snapshot when unavailable."
        )
        if self._last_error:
            notes_zh += f" 最近一次请求异常：{self._last_error}"
            notes_en += f" Last request error: {self._last_error}"

        return ProviderMeta(
            provider_name="AKShareFundProvider",
            source_label_zh="AKShare 开放式基金快照 + 历史净值",
            source_label_en="AKShare Open-Fund Snapshot + Historical NAV",
            data_mode="live",
            updated_at=updated_at,
            notes_zh=notes_zh,
            notes_en=notes_en,
        )
