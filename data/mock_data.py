"""Backward-compatible wrappers around the provider layer."""

from __future__ import annotations

import pandas as pd

from data.providers.registry import get_fund_data_provider


_provider = get_fund_data_provider()


def get_fund_snapshots() -> pd.DataFrame:
    return _provider.get_snapshots()


def search_fund(keyword: str) -> pd.DataFrame:
    return _provider.search(keyword)


def get_mock_trend(code: str, days: int = 60) -> pd.DataFrame:
    return _provider.get_trend(code, days=days)


def get_default_positions() -> pd.DataFrame:
    return _provider.get_default_positions()
