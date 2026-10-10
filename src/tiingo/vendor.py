"""Tiingo's end-of-day API, and its synthetic stand-in.

Two calls, and nothing else (https://www.tiingo.com/documentation/end-of-day):

- `GET /tiingo/daily/<ticker>`: a ticker's meta -- its name, the exchange
  Tiingo files it under (`NMFQS`, the Nasdaq Mutual Fund Quotation Service,
  for a mutual fund), and the first and last dates Tiingo has prices for;
- `GET /tiingo/daily/<ticker>/prices?startDate=...&endDate=...`: its daily
  prices over a range, one object a day: `date` (the day, at midnight UTC),
  `open`, `high`, `low`, `close`, `volume`, their adjusted forms, `divCash`
  and `splitFactor`, every number a JSON number. A mutual fund's `close` is
  its net asset value, which Tiingo has after midnight New York time.

The token goes in the `Authorization` header (`Token <token>`), never in an
address, so nothing kept or logged holds it. It is the plugin's secret
setting, entered by the person who holds the Tiingo account; this module
never prints it, and a response kept holds the address, status and body
alone.

Tiingo's free plan allows 50 requests an hour, 1,000 a day and 500 symbols a
month. The client keeps inside it: one request at a time, at most one every
two seconds, at most 45 in any hour and 950 in any day, refusing past that
(`OverBudget`) rather than being refused. The standard library's client: the
SDK carries none (the boundaries spec), and two calls need nothing more.

`SyntheticTiingo` answers the same calls from the responses under
synthetic/: shaped on Tiingo's documented responses, every value invented,
for VIGIX and VTSAX (mutual funds) and VOO (an ETF), and 404 for any other
ticker. No real Tiingo response is committed: the data is licensed for one
person's use.
"""

from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from importlib import resources
from typing import Any, Protocol

BASE = "https://api.tiingo.com"
USER_AGENT = "meridian-tiingo (+https://github.com/open-meridian/meridian-tiingo)"
#: The least time between two requests, in seconds.
SPACING = 2.0
TIMEOUT = 30.0
MOST_BYTES = 8 * 1024 * 1024
#: Inside the free plan's 50 an hour and 1,000 a day.
MOST_AN_HOUR = 45
MOST_A_DAY = 950
#: The free plan's limits, as Tiingo states them.
FREE_PLAN = "50 requests an hour, 1,000 a day, 500 symbols a month"
#: The exchange Tiingo files a mutual fund under.
MUTUAL_FUNDS = "NMFQS"


class Unreachable(Exception):  # noqa: N818 - what Tiingo was
    """Tiingo could not be asked: no answer, or not in time."""


class OverBudget(Exception):  # noqa: N818 - what the request would be
    """Asking now would go past the free plan's limits."""


def meta_path(ticker: str) -> str:
    return f"/tiingo/daily/{urllib.parse.quote(ticker.lower())}"


def prices_path(ticker: str, start: date, end: date) -> str:
    query = urllib.parse.urlencode({"startDate": start.isoformat(), "endDate": end.isoformat()})
    return f"{meta_path(ticker)}/prices?{query}"


@dataclass(frozen=True)
class Fetched:
    """One of Tiingo's responses, as received: never the request's headers."""

    path: str
    status: int
    body: bytes
    fetched_at: datetime

    @property
    def url(self) -> str:
        return BASE + self.path

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """The body as JSON, every number a Decimal: never a float."""
        from decimal import Decimal

        return json.loads(self.body, parse_float=Decimal, parse_int=Decimal)


class Tiingo(Protocol):
    mode: str
    budget: Budget

    async def get(self, path: str) -> Fetched: ...

    def today(self) -> date: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Budget:
    """The requests made in the last hour and day, by when."""

    hour: deque[float] = field(default_factory=deque)
    day: deque[float] = field(default_factory=deque)

    def take(self, now: float) -> None:
        for held, span in ((self.hour, 3600), (self.day, 86_400)):
            while held and held[0] <= now - span:
                held.popleft()
        if len(self.hour) >= MOST_AN_HOUR:
            raise OverBudget(f"{MOST_AN_HOUR} requests in the last hour, inside {FREE_PLAN}")
        if len(self.day) >= MOST_A_DAY:
            raise OverBudget(f"{MOST_A_DAY} requests in the last day, inside {FREE_PLAN}")
        self.hour.append(now)
        self.day.append(now)

    @property
    def used(self) -> tuple[int, int]:
        return len(self.hour), len(self.day)


class LiveTiingo:
    """Tiingo's API, with the token the person entered."""

    mode = "live"

    def __init__(self, token: str, now: Callable[[], datetime] = utc_now) -> None:
        self._token = token
        self._now = now
        self._lock = asyncio.Lock()
        self._last = 0.0
        self.budget = Budget()

    def __repr__(self) -> str:
        return "LiveTiingo(token=<withheld>)"

    def today(self) -> date:
        """Today in New York, where a fund's day is."""
        from zoneinfo import ZoneInfo

        return self._now().astimezone(ZoneInfo("America/New_York")).date()

    async def get(self, path: str) -> Fetched:
        async with self._lock:
            wait = self._last + SPACING - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self.budget.take(time.time())
            try:
                return await asyncio.to_thread(self._get, path)
            finally:
                self._last = time.monotonic()

    def _get(self, path: str) -> Fetched:
        request = urllib.request.Request(
            BASE + path,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Authorization": f"Token {self._token}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:  # noqa: S310 - Tiingo's https address
                body, status = answer.read(MOST_BYTES + 1), answer.status
        except urllib.error.HTTPError as refused:
            body = refused.read(MOST_BYTES + 1) if refused.fp else b""
            status = refused.code
        except (urllib.error.URLError, TimeoutError, OSError) as failed:
            reason = getattr(failed, "reason", failed)
            raise Unreachable(f"{BASE}{path.split('?')[0]}: {type(reason).__name__}") from failed
        if len(body) > MOST_BYTES:
            raise Unreachable(f"{BASE}{path.split('?')[0]}: answered more than {MOST_BYTES} bytes")
        return Fetched(path, status, body, self._now())


class SyntheticTiingo:
    """The synthetic responses under synthetic/, answering Tiingo's two calls
    as Tiingo would: a ticker's meta, and its prices over a range."""

    mode = "synthetic"
    #: The synthetic world's today: its last NAV is the day before.
    TODAY = date(2026, 10, 10)

    def __init__(self, now: Callable[[], datetime] = utc_now) -> None:
        self._now = now
        held = resources.files(__package__).joinpath("synthetic")
        self._meta: dict[str, bytes] = {}
        self._prices: dict[str, list[dict[str, Any]]] = {}
        for ticker in ("vigix", "vtsax", "voo"):
            self._meta[ticker] = held.joinpath(f"{ticker}-meta.json").read_bytes()
            self._prices[ticker] = json.loads(
                held.joinpath(f"{ticker}-prices.json").read_bytes(), parse_float=str
            )
        self.budget = Budget()

    def today(self) -> date:
        """The synthetic world's today, whatever the clock says: its
        responses end the day before, so a run on any day reads the same."""
        return self.TODAY

    async def get(self, path: str) -> Fetched:
        self.budget.take(time.time())
        parsed = urllib.parse.urlparse(path)
        parts = [p for p in parsed.path.split("/") if p]
        ticker = parts[2] if len(parts) >= 3 else ""
        if ticker not in self._meta:
            body = json.dumps({"detail": f"Error: Ticker '{ticker.upper()}' not found"})
            return Fetched(path, 404, body.encode(), self._now())
        if len(parts) == 3:
            return Fetched(path, 200, self._meta[ticker], self._now())
        query = urllib.parse.parse_qs(parsed.query)
        start = query.get("startDate", ["0000-00-00"])[0]
        end = query.get("endDate", ["9999-99-99"])[0]
        rows = [r for r in self._prices[ticker] if start <= r["date"][:10] <= end]
        if "startDate" not in query:
            rows = rows[-1:]
        # Re-serialised as received: the numbers' text is the file's.
        text = self._text(ticker, {r["date"] for r in rows})
        return Fetched(path, 200, text.encode(), self._now())

    def _text(self, ticker: str, dates: set[str]) -> str:
        """The prices file's objects for `dates`, each as its text in the
        file, so a number keeps the digits it was written with."""
        held = resources.files(__package__).joinpath("synthetic", f"{ticker}-prices.json")
        raw = held.read_text()
        objects = [o if o.startswith("{") else "{" + o for o in raw.strip("[]").split(",{")]
        kept = [o for o in objects if o[9:33] in dates]
        return "[" + ",".join(kept) + "]"


def tiingo(synthetic: bool, token: str, now: Callable[[], datetime] = utc_now) -> Tiingo | None:
    """Tiingo, synthetic or live; None where live is asked and no token is set."""
    if synthetic:
        return SyntheticTiingo(now)
    return LiveTiingo(token, now) if token else None
