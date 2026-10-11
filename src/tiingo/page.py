"""The plugin's pages, under Manage alone: the data role's common pages
(spec/plugin-pages-follow-their-role), Connection and Datasets, in its
order, each also a read tool for agents on the deployment's MCP under the
role's names (`read_connection`, `read_datasets`). Each record is the
role's (`meridian.roles.data`), extended with Tiingo's fields; each template
is the role's, with Tiingo's nuance at its blocks only.

A data plugin shows its connectivity, its data subscriptions and how its
entitlements resolve, and no market data (the product owner, 2026-10-03).
So:

- **Connection** (`/`): "Key" -- the mode (Live, Sample data or No key),
  the API token set or not (never shown), what Tiingo serves the token;
  "Limits and use" -- the free plan's limits it keeps, its requests, the
  last error; "Stream": it does not stream. Then Tiingo's rows: the last
  check, the requests this hour and today, the responses kept.
- **Datasets** (`/datasets`): "Served" -- the one dataset, as the catalogue
  declares it, licensed or not; "Wants" -- the standing wants it keeps
  current and the last wants answered; "Subjects". Then Tiingo's section:
  each fund listed, or read from the record a want named, one line each:
  what Tiingo says it is, whether it is served, the deployment's record for
  it or why there is none, the latest day recorded -- never a NAV --
  searched and paged by the kit's om-pager.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import meridian
from meridian.roles import data

from . import records
from .declaration import DAILY_DATASET, mode_name
from .feed import Feed, FundState, Status
from .settings import MOST_FUNDS
from .vendor import BASE, FREE_PLAN, MOST_A_DAY, MOST_AN_HOUR, MUTUAL_FUNDS

TITLE = "Tiingo"
#: The kit these pages are built on: 0.12.0's "Facts" and "Next step".
KIT = "0.12.0"

pages = meridian.Pages(TITLE, templates=Path(__file__).parent / "templates", kit=KIT)

CONNECTION = "/"
DATASETS = "/datasets"
#: The wants a browser is shown, the latest; the tool answers all.
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
        return "warn", "No key", "Set the API token in the plugin's Settings."
    if status.error and status.checked_at is not None and not status.recorded:
        return "error", "Not answering", status.error
    if status.error:
        return "warn", "Answering", status.error
    if status.checked_at is None:
        return "busy", "Reading Tiingo", ""
    if not status.funds:
        return "warn", "No fund listed", "Add one in the plugin's Settings, under Funds."
    if misses:
        tickers = ", ".join(sorted(f.ticker for f in misses))
        return "warn", f"{len(misses)} not resolved", tickers
    if status.mode == "synthetic":
        return "ok", "Sample data", ""
    return "ok", "Answering", ""


def _mode(status: Status) -> str:
    return {"synthetic": "Sample data", "waiting": "No key"}.get(status.mode, "Live")


def connection_read(status: Status, feed: Feed | None) -> records.ConnectionRead:
    state, said, _ = _state(status)
    used = feed.vendor.budget.used if feed is not None and feed.vendor is not None else (0, 0)
    kept = feed.raw.keys() if feed is not None else []
    window = ""
    if feed is not None and feed.raw.granted:
        window = "in the storage the deployment grants, as its responses settings say"
    elif feed is not None:
        window = "in a directory of the plugin's own: this deployment grants no storage"
    answered = status.mode == "synthetic" or (
        status.checked_at is not None and not (status.error and not status.recorded)
    )
    return records.ConnectionRead(
        mode=_mode(status),
        credentials=[data.Credential("API token", status.token_set)],
        entitled_at_vendor=(
            f"Mutual funds' daily NAVs, as far as the token's plan allows; the plugin keeps "
            f"inside the free plan's {FREE_PLAN}"
            if answered and status.mode != "waiting"
            else ""
        ),
        limit=(
            f"Tiingo's free plan: {FREE_PLAN}; the plugin asks at most {MOST_AN_HOUR} an "
            f"hour and {MOST_A_DAY} a day, one every two seconds"
        ),
        calls=status.fetches,
        rate_limited=status.rate_limited,
        last_call_at=_iso(status.checked_at),
        last_error=status.error,
        sessions=None,
        state=state,
        said=said,
        source=(
            "Recorded responses committed with the plugin, every value invented"
            if status.mode == "synthetic"
            else f"{BASE}/tiingo/daily, end-of-day prices"
        ),
        checked_at=_iso(status.checked_at),
        requests_last_hour=used[0],
        requests_last_day=used[1],
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


def _want(answered: Any) -> records.Want:
    declined = ", ".join(f"{n} {reason.replace('_', ' ')}" for reason, n in answered.declined)
    return records.Want(
        dataset="",
        asked=answered.asked,
        subjects=answered.subjects,
        recorded=answered.recorded,
        declined=sum(n for _, n in answered.declined),
        state="Answered, standing" if answered.standing else "Answered",
        want_id=answered.want_id,
        at=_iso(answered.at),
        standing=answered.standing,
        declined_as=declined,
    )


def datasets_read(status: Status, feed: Feed | None) -> records.DatasetsRead:
    instance = feed.plugin.identity.instance_id if feed is not None else "tiingo"
    entry = DAILY_DATASET
    dataset = f"{instance}:{entry.key}"
    connection = connection_read(status, feed)
    if connection.mode == "Sample data":
        at_vendor = "Yes"
    elif connection.mode == "No key" or not connection.entitled_at_vendor:
        at_vendor = "Not asked yet"
    else:
        at_vendor = "Yes, as the token's plan allows"
    served = [
        records.Served(
            dataset=dataset,
            data="mutual funds' NAVs",
            arrives=", ".join(mode_name(m) for m in entry.modes),
            day="New York's, to 16:00",
            default_terms="kept; personal use",
            entitled_at_vendor=at_vendor,
            recorded=status.recorded,
            declined=status.declined,
            last_recorded=_iso(status.last_recorded_at),
            licensed=dataset in status.licensed,
            history="each fund's own, from the date Tiingo's prices for it begin",
            venue="none: a fund strikes its NAV on no venue",
            restated=status.restated,
            unchanged=status.unchanged,
        )
    ]
    standing = [
        records.Want(
            dataset=dataset,
            asked="nav",
            subjects=n,
            state="Kept current",
            want_id=want_id,
            at=_iso(since),
            standing=True,
        )
        for want_id, (n, since) in status.standing.items()
    ]
    answered = [replace(_want(a), dataset=dataset) for a in status.wants]
    return records.DatasetsRead(
        served=served,
        wants=standing + answered,
        reads_instruments=status.reads_instruments,
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
    )


def figures(status: Status, feed: Feed | None) -> list[meridian.Figure]:
    """The data role's figures, in its order (`meridian.roles.data`); Tiingo
    reports none of its own."""
    read = connection_read(status, feed)
    state, said, why = _state(status)
    if read.mode in ("Sample data", "No key"):
        connection: Any = read.mode
    elif state == "error":
        connection = meridian.Figure("", "Not answering", state="error", why=why[:200])
    else:
        connection = meridian.Figure(
            "", "Answering", state="warn" if status.error else None, why=status.error[:200]
        )
    hour = read.requests_last_hour
    return data.figures(
        connection=connection,
        entitled_at_vendor=None if read.mode == "No key" else "1 of 1 datasets",
        stream="Does not stream",
        last_recorded=status.last_recorded_at,
        rate_use=meridian.Figure(
            "",
            f"{hour} of {MOST_AN_HOUR} an hour",
            state="warn" if hour * 5 >= MOST_AN_HOUR * 4 else None,
            why=f"{status.rate_limited} answered 429" if status.rate_limited else "",
        ),
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
        "How this plugin reaches Tiingo, as every data plugin's Connection answers it: the "
        "mode (Live, Sample data or No key), the API token set or not (never shown), what "
        "Tiingo serves the token, the free plan's limits it keeps and its requests, the "
        "last check and error; it does not stream. Then Tiingo's own: the source, the "
        "requests this hour and today, and how many responses are kept. No price."
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
        "What this plugin serves the lake, as every data plugin's Datasets answers it: its "
        "one dataset as the catalogue declares it (mutual funds' daily NAVs, New York's "
        "day ending at 16:00, one person's terms), whether a deployment admin has licensed "
        "it, what it recorded and declined; the standing wants it keeps current and the "
        "wants it answered; whether it may read an instrument's record. Then Tiingo's own: "
        "each fund listed with what Tiingo says it is, whether it is served, the "
        f"deployment's record for it or why there is none, up to {MOST_FUNDS}. No NAV."
    ),
)
async def datasets(request: meridian.Request) -> meridian.Response:
    status, feed = _status()
    read = datasets_read(status, feed)
    # A browser's search narrows the funds drawn, and it is drawn the latest
    # wants; a tool answers them all.
    query = request.query.get("q", "").strip()[:MOST_QUERY]
    shown = [f for f in read.funds if matching(query, f.ticker, f.name, f.at_tiingo)]
    drawn = read if request.tool_name else replace(read, wants=read.wants[:SHOWN_WANTS])
    return pages.answer(
        "datasets.html",
        drawn,
        query=query,
        shown=shown,
        state=_state(status),
        checked_at=_iso(status.checked_at),
        wants=len(read.wants),
    )
