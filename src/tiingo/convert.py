"""Tiingo's daily prices for a mutual fund, as the lake's net asset values.

A mutual fund does not trade on an exchange: it is bought and sold at the net
asset value per share it strikes once a business day, at the close in New
York. Tiingo files a mutual fund under `NMFQS` and gives its NAV as the day's
`close` (its open, high and low are the same number, its volume 0). So each
of Tiingo's days for a fund is one price:

- **kind** `nav`, a fund's net asset value per share for the business date;
  basis `per_unit`; in US dollars, which Tiingo prices these funds in;
- **business_date** the day Tiingo gives (`2026-10-08T00:00:00.000Z` is 8
  October 2026): a plain date, in the day the dataset declares, New York's,
  ending at 16:00, when funds strike their NAV;
- **valid from and until** that declared day: 16:00 the day before to 16:00
  on the date, New York time;
- **row key** the ticker and the date (`VIGIX:2026-10-08`): read again from
  any response, a repeat; a NAV Tiingo corrects is the row's next version;
- **no source time:** Tiingo states none, so none is sent (never a time the
  plugin chose);
- **raw** the response it was read from, kept in the plugin's storage.

Each number is made a Decimal from the JSON's text, never a float. A day
whose `close` is missing or not a number is not a price, and is returned as
not converted, its text kept.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from meridian import Money, ObservationMeta, Price
from meridian.plugin.v1 import operations_pb2 as ops

#: The day the dataset declares: New York's, ending at 16:00.
DAY_TIME_ZONE = "America/New_York"
DAY_END_MINUTE = 16 * 60
NEW_YORK = ZoneInfo(DAY_TIME_ZONE)
#: The currency Tiingo prices these funds in.
CURRENCY = "USD"


def _ns(moment: datetime) -> int:
    return int(moment.timestamp()) * 10**9


def day_bounds(day: date) -> tuple[int, int]:
    """The declared day for business date `day`: 16:00 the day before to
    16:00 on it, New York time, in nanoseconds since the epoch."""
    close = time(DAY_END_MINUTE // 60, DAY_END_MINUTE % 60)
    end = datetime.combine(day, close, NEW_YORK)
    start = datetime.combine(day - timedelta(days=1), close, NEW_YORK)
    return _ns(start), _ns(end)


def row_key(ticker: str, day: date) -> str:
    return f"{ticker.upper()}:{day.isoformat()}"


@dataclass(frozen=True)
class Nav:
    """One day's net asset value, as Tiingo gave it."""

    ticker: str
    day: date
    value: Decimal


@dataclass(frozen=True)
class Read:
    """A response's days as NAVs, and what of it did not convert."""

    navs: tuple[Nav, ...]
    unconverted: tuple[str, ...]


def navs(ticker: str, body: Any) -> Read:
    """The NAVs a prices response states, read with every number a Decimal
    (`Fetched.json`)."""
    found: list[Nav] = []
    unconverted: list[str] = []
    for row in body if isinstance(body, list) else []:
        stated = row.get("date") if isinstance(row, dict) else None
        close = row.get("close") if isinstance(row, dict) else None
        try:
            day = date.fromisoformat(str(stated)[:10])
        except ValueError:
            unconverted.append(f"a day that is no date: {stated!r}")
            continue
        if not isinstance(close, Decimal) or not close.is_finite() or close <= 0:
            unconverted.append(f"{day}: a close that is no price: {close!r}")
            continue
        found.append(Nav(ticker.upper(), day, close))
    return Read(tuple(found), tuple(unconverted))


def to_prices(
    held: Iterable[Nav],
    subject: str,
    *,
    dataset: str,
    raw: Sequence[ops.RawRecordRef] | ops.RawRecordRef,
) -> list[Price]:
    """Each NAV as the price of the fund's instrument `subject`; `raw` is the
    response each was read from, one for all or one each."""
    navs_held = list(held)
    refs = [raw] * len(navs_held) if isinstance(raw, ops.RawRecordRef) else list(raw)
    out: list[Price] = []
    for nav, ref in zip(navs_held, refs, strict=True):
        start, end = day_bounds(nav.day)
        out.append(
            Price(
                meta=ObservationMeta(
                    row_key=row_key(nav.ticker, nav.day),
                    subjects=[ops.SubjectRef(entity_id=subject)],
                    source=ops.Source(dataset=dataset),
                    valid_from_ns=start,
                    valid_until_ns=end,
                    business_date=nav.day,
                    raw=ref,
                ),
                kind="nav",
                price=Money(nav.value, CURRENCY),
                basis="per_unit",
            )
        )
    return out
