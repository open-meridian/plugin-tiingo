"""Tiingo's days for a fund as the lake's net asset values."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal

from meridian import ObservationMeta, Price
from meridian.plugin.v1 import operations_pb2 as ops

from tiingo.convert import day_bounds, navs, to_prices

from conftest import DATASET

RAW = ops.RawRecordRef(instance_id="tiingo", key="responses/2026-10/x.json.gz")
BODY = (
    '[{"date":"2026-10-08T00:00:00.000Z","close":245.55,"high":245.55,"low":245.55,'
    '"open":245.55,"volume":0,"adjClose":245.55,"divCash":0.0,"splitFactor":1.0},'
    '{"date":"2026-10-09T00:00:00.000Z","close":243.9,"volume":0}]'
)


def meta(price: Price) -> ObservationMeta:
    assert price.meta is not None
    return price.meta


def read() -> list[Price]:
    found = navs("vigix", json.loads(BODY, parse_float=Decimal, parse_int=Decimal))
    return to_prices(found.navs, "LCL-VIGIX", dataset=DATASET, raw=RAW)


def test_a_days_close_is_the_funds_nav() -> None:
    first, second = read()
    assert first.kind == "nav" and first.basis == "per_unit"
    assert first.price.amount == Decimal("245.55") and first.price.currency_code == "USD"
    assert second.price.amount == Decimal("243.9")
    assert meta(first).row_key == "VIGIX:2026-10-08"
    assert meta(first).business_date == date(2026, 10, 8)
    assert [s.entity_id for s in meta(first).subjects] == ["LCL-VIGIX"]
    source = meta(first).source
    assert source is not None and source.dataset == DATASET and not source.venue_id
    assert meta(first).raw == RAW
    # Tiingo states no time of its own, so none is sent.
    assert not meta(first).source_times


def test_the_declared_day_ends_at_four_in_new_york() -> None:
    start, end = day_bounds(date(2026, 10, 8))
    assert datetime.fromtimestamp(end // 10**9, UTC) == datetime(2026, 10, 8, 20, 0, tzinfo=UTC)
    assert datetime.fromtimestamp(start // 10**9, UTC) == datetime(2026, 10, 7, 20, 0, tzinfo=UTC)
    first, _ = read()
    assert (meta(first).valid_from_ns, meta(first).valid_until_ns) == (start, end)


def test_a_day_that_is_no_price_is_not_converted() -> None:
    body = [{"date": "2026-10-08T00:00:00.000Z", "close": None}, {"date": "soon", "close": 1}]
    found = navs("VIGIX", body)
    assert not found.navs and len(found.unconverted) == 2
