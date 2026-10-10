"""The plugin's pages, under Manage alone: Connection and Datasets, each
also a read tool for agents on the deployment's MCP (`read_connection`,
`read_datasets`; plans/the-lake-prices-the-book, "v18's names").

A `dgm` shows its connectivity, its data subscriptions and how its
entitlements resolve, and no market data (the product owner, 2026-10-03).
So:

- **Connection** (`/`): how the plugin reaches Tiingo -- live, synthetic, or
  waiting for its token (said to be set or not, never shown) -- the last
  check and why it failed, the requests made against the free plan's limits
  it keeps, and the responses kept.
- **Datasets** (`/datasets`): the one dataset the catalogue declares; the
  standing wants it keeps current and the last wants answered; and each fund
  listed, or read from the record a want named, one line each: what Tiingo
  says it is, whether it is served, the deployment's record for it or why
  there is none, its history's start and the latest day recorded -- never a
  NAV -- paged by the kit's om-pager.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import meridian

from . import records
from .declaration import CADENCE, DAILY_DATASET, VENDOR, mode_name
from .feed import Feed, FundState, Status
from .settings import MOST_FUNDS
from .vendor import BASE, FREE_PLAN, MOST_A_DAY, MOST_AN_HOUR, MUTUAL_FUNDS

TITLE = "Tiingo"
# The kit these pages were built against: 0.10.0, every page one screen.
KIT = "0.10.0"

pages = meridian.Pages(TITLE, templates=Path(__file__).parent / "templates", kit=KIT)

CONNECTION = "/"
DATASETS = "/datasets"
SHOWN_WANTS = 3
#: The longest search the Datasets tab reads.
MOST_QUERY = 100
_LABELS = {"tiingo_api_token": "API token"}

_held: dict[str, Feed] = {}


def hold(feed: Feed) -> None:
    _held["feed"] = feed


def _status() -> tuple[Status, Feed | None]:
    feed = _held.get("feed")
    return (feed.status if feed is not None else Status(), feed)


def _iso(moment: datetime | None) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds") if moment else ""


def _state(status: Status) -> tuple[str, str, str]:
    misses = [f for f in status.funds.values() if f.mutual_fund and f.miss]
    if status.mode == "waiting":
        return "warn", "Waiting for the API token", "Set it in the plugin's Settings."
    if status.error and status.checked_at is not None and not status.recorded:
        return "error", "Tiingo was not read", status.error
    if status.error:
        return "warn", "The last check failed", status.error
    if status.checked_at is None:
        return "busy", "Reading Tiingo", ""
    if not status.funds:
        return "warn", "No fund listed", "Add one in the plugin's Settings, under Funds."
    if misses:
        tickers = ", ".join(sorted(f.ticker for f in misses))
        return "warn", f"{len(misses)} not resolved", tickers
    return "ok", "Tiingo read", ""


def connection_read(status: Status, feed: Feed | None) -> records.ConnectionRead:
    state, said, _ = _state(status)
    used = feed.vendor.budget.used if feed is not None and feed.vendor is not None else (0, 0)
    kept = feed.raw.keys() if feed is not None else []
    window = ""
    if feed is not None and feed.raw.granted:
        window = "in the storage the deployment grants, as its responses settings say"
    elif feed is not None:
        window = "in a directory of the plugin's own: this deployment grants no storage"
    return records.ConnectionRead(
        mode=status.mode,
        state=state,
        said=said,
        token_set=status.token_set,
        waiting_for=[_LABELS.get(name, name) for name in status.missing],
        source=(
            "Synthetic responses committed with the plugin, every value invented"
            if status.mode == "synthetic"
            else f"{BASE}/tiingo/daily, end-of-day prices"
        ),
        checked_at=_iso(status.checked_at),
        error=status.error,
        requests_last_hour=used[0],
        requests_last_day=used[1],
        limits=(
            f"Tiingo's free plan: {FREE_PLAN}. The plugin asks one request at a time, at most "
            f"one every two seconds, and at most {MOST_AN_HOUR} an hour and {MOST_A_DAY} a day; "
            "it reads each listed fund every six hours."
        ),
        pages_read=status.fetches,
        responses_kept=len(kept),
        kept_for=window,
    )


def _at_tiingo(fund: FundState) -> str:
    if fund.found == "not_found":
        return "not found"
    if not fund.found:
        return "not asked yet"
    if fund.exchange.upper() == MUTUAL_FUNDS:
        return "mutual fund"
    return f"not a mutual fund ({fund.exchange or 'no exchange'})"


def _want(answered: Any) -> records.WantRead:
    declined = ", ".join(f"{n} {reason.replace('_', ' ')}" for reason, n in answered.declined)
    return records.WantRead(
        answered.want_id,
        answered.asked,
        answered.subjects,
        answered.recorded,
        declined,
        _iso(answered.at),
        answered.standing,
    )


def datasets_read(status: Status, feed: Feed | None) -> records.DatasetsRead:
    instance = feed.plugin.identity.instance_id if feed is not None else "tiingo"
    entry = DAILY_DATASET
    return records.DatasetsRead(
        dataset=records.DatasetRead(
            dataset=f"{instance}:{entry.key}",
            vendor=VENDOR,
            data_types=list(entry.data_types),
            modes=[mode_name(m) for m in entry.modes],
            cadence="daily" if entry.cadence == CADENCE else f"{entry.cadence} s",
            day="New York's, ending at 16:00 (America/New_York, 16:00)",
            history="Each fund's own, from the date Tiingo's prices for it begin",
            venue="None: a fund strikes its NAV on no venue",
            licence=(
                "One person's terms: Tiingo's free and Power plans are for internal and "
                "personal use, no redistribution; kept, used and shown to that person"
            ),
        ),
        entitled_at_vendor=(
            f"Whatever the token's plan allows; the plugin keeps inside the free plan's "
            f"{FREE_PLAN}, and reads only the funds listed and those a want names by a "
            f"record carrying a ticker, {MOST_FUNDS} in all."
        ),
        funds=[
            records.FundRead(
                ticker=f.ticker,
                name=f.name,
                at_tiingo=_at_tiingo(f),
                served=f.served,
                instrument_id=f.instrument_id,
                from_setting=bool(f.configured),
                from_want=f.wanted,
                miss=f.miss.replace("_", " "),
                history_from=f.start,
                latest_recorded=f.latest,
            )
            for f in sorted(
                [*status.funds.values(), *status.read.values()],
                key=lambda f: (f.ticker, f.wanted),
            )
        ],
        unconverted=list(status.unconverted),
        standing=[
            records.WantRead(want_id, "kept current", n, 0, "", _iso(since), True)
            for want_id, (n, since) in status.standing.items()
        ],
        wants=[_want(a) for a in status.wants],
    )


def _moment(value: str) -> str:
    if not value:
        return ""
    if len(value) == 10:
        return value
    return datetime.fromisoformat(value).astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _day(value: str) -> str:
    return date.fromisoformat(value).strftime("%a %d %b") if value else ""


def matching(query: str, *texts: str) -> bool:
    """Whether every word of a search is in one of `texts`, case aside."""
    words = query.lower().split()
    held = " ".join(texts).lower()
    return all(word in held for word in words)


pages.environment.filters["moment"] = _moment
pages.environment.filters["day"] = _day


@pages.page(
    CONNECTION,
    "Connection",
    levels="admin",
    answers=records.ConnectionRead,
    name="read_connection",
    description=(
        "How this plugin reaches Tiingo: live, synthetic, or waiting for its API token "
        "(said to be set or not, never shown), the last check and why it failed if it did, "
        "the requests made against the free plan's limits it keeps, and how many responses "
        "are kept. No price."
    ),
)
async def connection(request: meridian.Request) -> meridian.Response:
    status, feed = _status()
    return pages.answer("connection.html", connection_read(status, feed), detail=_state(status)[2])


@pages.page(
    DATASETS,
    "Datasets",
    levels="admin",
    answers=records.DatasetsRead,
    name="read_datasets",
    description=(
        "What this plugin serves the lake: its one dataset as the catalogue declares it "
        "(mutual funds' daily NAVs, New York's day ending at 16:00, one person's terms), each "
        "fund listed with what Tiingo says it is, whether it is served, the deployment's "
        "record for it or why there is none and the latest day recorded, the standing wants "
        "it keeps current and the wants it answered lately. No NAV."
    ),
)
async def datasets(request: meridian.Request) -> meridian.Response:
    status, feed = _status()
    data = datasets_read(status, feed)
    # A browser's search narrows the rows drawn; a tool answers them all.
    query = request.query.get("q", "").strip()[:MOST_QUERY]
    shown = [f for f in data.funds if matching(query, f.ticker, f.name, f.at_tiingo)]
    return pages.answer(
        "datasets.html",
        data,
        query=query,
        shown=shown,
        state=_state(status),
        checked_at=_iso(status.checked_at),
        shown_wants=data.wants[:SHOWN_WANTS],
    )
