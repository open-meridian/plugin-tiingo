"""Tiingo's two calls, the synthetic stand-in, and the limits kept."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tiingo.vendor import (
    MOST_AN_HOUR,
    Budget,
    LiveTiingo,
    OverBudget,
    SyntheticTiingo,
    meta_path,
    prices_path,
    tiingo,
)

from conftest import AT


def test_the_addresses_never_hold_a_token() -> None:
    assert meta_path("VIGIX") == "/tiingo/daily/vigix"
    path = prices_path("VIGIX", date(2026, 10, 1), date(2026, 10, 9))
    assert path == "/tiingo/daily/vigix/prices?startDate=2026-10-01&endDate=2026-10-09"
    assert "token" not in path


def test_the_token_is_withheld_from_a_repr() -> None:
    live = LiveTiingo("abc123secret")
    assert "abc123secret" not in repr(live)
    assert tiingo(False, "") is None
    assert isinstance(tiingo(True, ""), SyntheticTiingo)


async def test_synthetic_meta_and_prices_as_tiingo_answers_them() -> None:
    synthetic = SyntheticTiingo(lambda: AT)
    meta = (await synthetic.get(meta_path("VIGIX"))).json()
    assert meta["exchangeCode"] == "NMFQS" and meta["startDate"] == "1998-05-14"
    prices = await synthetic.get(prices_path("VIGIX", date(2026, 10, 7), date(2026, 10, 9)))
    rows = prices.json()
    assert [r["date"][:10] for r in rows] == ["2026-10-07", "2026-10-08", "2026-10-09"]
    assert rows[1]["close"] == Decimal("245.55") and isinstance(rows[1]["close"], Decimal)
    missing = await synthetic.get(meta_path("NOSUCH"))
    assert missing.status == 404 and "not found" in missing.text


def test_the_free_plans_limits_are_kept() -> None:
    budget = Budget()
    for n in range(MOST_AN_HOUR):
        budget.take(1000.0 + n)
    with pytest.raises(OverBudget, match="last hour"):
        budget.take(1100.0)
    budget.take(1000.0 + 3600.5)
    assert budget.used[0] == MOST_AN_HOUR
