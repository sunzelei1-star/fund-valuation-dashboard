#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import sys


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    os.environ["FUND_DATA_PROVIDER"] = "akshare_live"

    try:
        from data.providers.registry import get_fund_data_provider
        from data.providers.mock_provider import LocalMockFundProvider
    except ModuleNotFoundError as exc:
        print(f"dependency_error={exc}")
        print("hint=please install requirements first: pip install -r requirements.txt")
        return 1

    provider = get_fund_data_provider()
    print(f"provider={provider.__class__.__name__}")
    meta = provider.get_meta()
    print(f"provider_mode={meta.data_mode}")

    try:
        snapshots = provider.get_snapshots()
        print(f"snapshots_rows={len(snapshots)}")
        print(f"provider_updated_at={provider.get_meta().updated_at.isoformat()}")
        print(f"provider_note={provider.get_meta().notes_zh}")
        if snapshots.empty:
            print("warning=AKShare returned empty snapshot table")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"akshare_error={exc}")
        fallback = LocalMockFundProvider()
        fallback_rows = len(fallback.get_snapshots())
        print(f"fallback_provider={fallback.__class__.__name__}")
        print(f"fallback_snapshots_rows={fallback_rows}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
