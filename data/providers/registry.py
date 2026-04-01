from __future__ import annotations

import os

from data.providers.akshare_provider import AKShareFundProvider
from data.providers.base import FundDataProvider
from data.providers.mock_provider import LocalMockFundProvider


def get_fund_data_provider() -> FundDataProvider:
    provider_name = os.getenv("FUND_DATA_PROVIDER", "local_mock").lower()
    if provider_name == "local_mock":
        return LocalMockFundProvider()
    if provider_name == "akshare_live":
        return AKShareFundProvider()

    # fallback to deterministic local provider for safety and offline reproducibility
    return LocalMockFundProvider()
