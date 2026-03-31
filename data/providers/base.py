from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import pandas as pd


@dataclass(frozen=True)
class ProviderMeta:
    provider_name: str
    source_label_zh: str
    source_label_en: str
    data_mode: str  # mock | hybrid | live
    updated_at: datetime
    notes_zh: str
    notes_en: str


class FundDataProvider(Protocol):
    def get_catalog(self) -> pd.DataFrame:
        """Return fund master catalog with code/name_zh/name_en/category."""

    def get_snapshots(self) -> pd.DataFrame:
        """Return latest snapshot with nav/est_nav/day_change_pct."""

    def get_trend(self, code: str, days: int = 90) -> pd.DataFrame:
        """Return trend series with date/nav/est_nav columns."""

    def search(self, keyword: str) -> pd.DataFrame:
        """Search funds in snapshots and return filtered dataframe."""

    def get_default_positions(self) -> pd.DataFrame:
        """Return default portfolio positions."""

    def get_meta(self) -> ProviderMeta:
        """Return provider metadata for data source disclosure."""
