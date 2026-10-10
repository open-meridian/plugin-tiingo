"""Tiingo's NAVs into the lake: each listed fund's latest pushed every few
hours, and any past day recorded when the lake wants it (W10.4, W10.7).

**The funds.** The Funds setting lists each mutual fund by its ticker. For
each, Tiingo's meta says whether it is one: a fund Tiingo files under
`NMFQS` is served; anything else (an ETF, a stock) is shown on the Datasets
tab as not a mutual fund and not recorded -- its closes are the equity
datasets' -- and a ticker Tiingo does not know is shown as not found.

**Subjects.** A fund's subject is the deployment's record the Funds row names
where it names one; otherwise its ticker resolved as Tiingo's symbol
(`symbol` VIGIX from source `tiingo`, W3.1), with what Tiingo states of it --
a fund, in US dollars, its name -- and a miss reported with why (W3.2).

**Push.** At start, when the settings change and every six hours, each
served fund's prices for the last ten days are read and recorded, in batches
of at most 500. Each NAV read again names the response it was first read
from at that value (raw.py), so the lake answers it unchanged; a NAV Tiingo
corrected is the row's next version.

**Wants.** The lake asks for a fund's NAVs it does not hold: a business date,
a range, or the latest. A subject that is no served fund is declined
`not_covered`; a day before the fund's history at Tiingo `beyond_history`;
a day Tiingo has no NAV for yet, or that it cannot be asked for now (its
limits, or no answer), `source_silent`. A standing want is kept current by
the push, and listed until withdrawn.

**Tiingo's limits** are kept by the client (vendor.py); a token Tiingo
refuses stops reading until the settings change, and says so.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import meridian
from meridian.plugin.v1 import operations_pb2 as ops

from .convert import NEW_YORK, Nav, navs, to_prices
from .declaration import DAILY
from .raw import RawStore
from .settings import Config, Fund
from .vendor import (
    MUTUAL_FUNDS,
    Fetched,
    OverBudget,
    Tiingo,
    Unreachable,
    meta_path,
    prices_path,
    tiingo,
    utc_now,
)

log = logging.getLogger("tiingo")

#: The source this plugin names its symbols and its misses by.
SOURCE = "tiingo"
BATCH = 500
#: How far back each check reads a fund's prices.
LOOKBACK_DAYS = 10
#: The most days one want is answered for: a year.
MOST_DAYS = 366
RECENT = 12


def _ns(moment: datetime) -> int:
    return int(moment.timestamp() * 1_000_000) * 1000


@dataclass
class FundState:
    """One listed fund as the plugin last found it at Tiingo."""

    ticker: str
    configured: str = ""
    name: str = ""
    exchange: str = ""
    start: str = ""
    end: str = ""
    #: `found`, `not_found` (Tiingo knows no such ticker), or empty: not asked.
    found: str = ""
    instrument_id: str = ""
    miss: str = ""
    latest: str = ""

    @property
    def mutual_fund(self) -> bool:
        return self.found == "found" and self.exchange.upper() == MUTUAL_FUNDS

    @property
    def served(self) -> bool:
        return self.mutual_fund and bool(self.instrument_id)


@dataclass(frozen=True)
class Answered:
    want_id: str
    asked: str
    subjects: int
    recorded: int
    declined: tuple[tuple[str, int], ...]
    at: datetime
    standing: bool = False


@dataclass
class Status:
    """What the plugin last did, for its pages; held in memory."""

    mode: str = "waiting"
    token_set: bool = False
    missing: tuple[str, ...] = ()
    started_at: datetime | None = None
    checked_at: datetime | None = None
    error: str = ""
    recorded: int = 0
    restated: int = 0
    unchanged: int = 0
    funds: dict[str, FundState] = field(default_factory=dict)
    unconverted: list[str] = field(default_factory=list)
    wants: list[Answered] = field(default_factory=list)
    standing: dict[str, tuple[int, datetime]] = field(default_factory=dict)
    fetches: int = 0


@dataclass(frozen=True)
class Outcome:
    recorded: int = 0
    restated: int = 0
    unchanged: int = 0

    def __add__(self, other: Outcome) -> Outcome:
        return Outcome(
            self.recorded + other.recorded,
            self.restated + other.restated,
            self.unchanged + other.unchanged,
        )


class Feed:
    """The plugin's work, on its typed operations -- `plugin` is the
    connected `meridian.Plugin`, or the suite's `Recorder` in its tests --
    reading Tiingo, resolving, recording, answering wants."""

    def __init__(
        self,
        plugin: Any,
        raw: RawStore,
        now: Callable[[], datetime] = utc_now,
        vendor: Tiingo | None = None,
    ) -> None:
        self.plugin = plugin
        self.raw = raw
        self.now = now
        self.vendor = vendor
        self.status = Status(started_at=now(), mode=vendor.mode if vendor else "waiting")
        self._keyed: tuple[bool, str] | None = None

    @property
    def dataset(self) -> str:
        return f"{self.plugin.identity.instance_id}:{DAILY}"

    def configure(self, config: Config) -> None:
        """Take a delivery of the settings: the token and mode, and the funds."""
        keyed = (config.synthetic, config.token)
        if keyed != self._keyed:
            self._keyed = keyed
            self.vendor = tiingo(config.synthetic, config.token, self.now)
            self.status.error = ""
            for fund in self.status.funds.values():
                fund.found, fund.latest = "", ""
        self.status.mode = self.vendor.mode if self.vendor is not None else "waiting"
        self.status.token_set = bool(config.token)
        self.status.missing = config.missing
        held = self.status.funds
        self.status.funds = {}
        for listed in config.funds:
            state = held.get(listed.ticker) or FundState(listed.ticker)
            if state.configured != listed.instrument_id:
                state.instrument_id, state.miss = "", ""
            state.configured = listed.instrument_id
            self.status.funds[listed.ticker] = state

    def configured(self, funds: Iterable[Fund]) -> None:
        """Set the funds alone, for a test or a preview."""
        self.configure(
            Config(
                token="",
                funds=tuple(funds),
                synthetic=self.vendor is not None and self.vendor.mode == "synthetic",
            )
        )

    # ── Reading Tiingo ──────────────────────────────────────────────────

    async def fetch(self, path: str) -> tuple[Fetched, str]:
        """One of Tiingo's responses, kept before it is read."""
        if self.vendor is None:
            raise Unreachable("no token is set")
        fetched = await self.vendor.get(path)
        self.status.fetches += 1
        if fetched.status in (401, 403):
            # Never the token: Tiingo's own words would not hold it, but the
            # plugin says only what happened.
            raise Unreachable(f"Tiingo refused the token ({fetched.status})")
        if fetched.status == 429:
            raise OverBudget("Tiingo answered 429: its limit for the token was reached")
        return fetched, self.raw.keep(fetched)

    async def meta(self, fund: FundState) -> None:
        fetched, _ = await self.fetch(meta_path(fund.ticker))
        if fetched.status == 404:
            fund.found = "not_found"
            return
        if fetched.status != 200:
            raise Unreachable(f"Tiingo answered {fetched.status} for {fund.ticker}")
        body = fetched.json()
        fund.found = "found"
        fund.name = str(body.get("name") or "")
        fund.exchange = str(body.get("exchangeCode") or "")
        fund.start = str(body.get("startDate") or "")[:10]
        fund.end = str(body.get("endDate") or "")[:10]

    async def resolve(self, fund: FundState) -> None:
        """The fund's subject: the record its row names, or its ticker
        resolved as Tiingo's symbol, a miss reported."""
        if fund.instrument_id:
            return
        if fund.configured:
            fund.instrument_id, fund.miss = fund.configured, ""
            return
        identifier = ops.Identifier(scheme="symbol", value=fund.ticker, source=SOURCE)
        found = await self.plugin.resolve_identifier(
            identifiers=[identifier],
            stated_asset_class="fund",
            stated_currency="USD",
            stated_description=fund.name,
        )
        if found.found and found.instrument_id:
            fund.instrument_id, fund.miss = found.instrument_id, ""
            return
        reason = found.miss_reason or ops.MISS_REASON_NOT_FOUND
        fund.miss = ops.MissReason.Name(reason).removeprefix("MISS_REASON_").lower()
        await self.plugin.report_missing_instrument(
            source=SOURCE,
            asset_class="fund",
            identifiers=[identifier],
            reason=reason,
            observed_at_ns=_ns(self.now()),
        )

    # ── Recording ───────────────────────────────────────────────────────

    async def record(
        self,
        fund: FundState,
        fetched: Fetched,
        key: str,
        *,
        want_id: str = "",
        days: Sequence[date] | None = None,
    ) -> Outcome:
        """Record the NAVs a prices response states -- on `days` where given
        -- against `want_id` where given."""
        read = navs(fund.ticker, fetched.json())
        for said in read.unconverted:
            self.status.unconverted = [f"{fund.ticker} {said}", *self.status.unconverted][:RECENT]
        held: list[Nav] = [n for n in read.navs if days is None or n.day in set(days)]
        if not held:
            return Outcome()
        firsts = self.raw.note_first(fund.ticker, {f"{n.day}:{n.value}": key for n in held})
        refs = [self.plugin.raw_record(firsts[f"{n.day}:{n.value}"]) for n in held]
        prices = to_prices(held, fund.instrument_id, dataset=self.dataset, raw=refs)
        outcome = Outcome()
        for start in range(0, len(prices), BATCH):
            done = await self.plugin.record_prices(
                prices=prices[start : start + BATCH], want_id=want_id
            )
            outcome = outcome + Outcome(done.recorded, done.restated, done.unchanged)
        latest = max(n.day for n in held).isoformat()
        fund.latest = max(fund.latest, latest)
        self.status.recorded += outcome.recorded
        self.status.restated += outcome.restated
        self.status.unchanged += outcome.unchanged
        return outcome

    async def prepare(self, fund: FundState) -> bool:
        """Ask Tiingo about the fund where not yet, and resolve it where it
        is a mutual fund; whether it is served."""
        if not fund.found:
            await self.meta(fund)
        if fund.mutual_fund:
            await self.resolve(fund)
        return fund.served

    async def check(self) -> Outcome | None:
        """Read each listed fund's last days and record them. None where
        there is nothing to read with."""
        self.status.checked_at = self.now()
        if self.vendor is None:
            return None
        total = Outcome()
        today = self.vendor.today()
        try:
            for fund in list(self.status.funds.values()):
                if not await self.prepare(fund):
                    continue
                path = prices_path(fund.ticker, today - timedelta(days=LOOKBACK_DAYS), today)
                fetched, key = await self.fetch(path)
                if fetched.status != 200:
                    raise Unreachable(f"Tiingo answered {fetched.status} for {fund.ticker}")
                done = await self.record(fund, fetched, key)
                total = total + done
                log.info(
                    "%s: %d NAVs recorded, %d restated, %d unchanged",
                    fund.ticker,
                    done.recorded,
                    done.restated,
                    done.unchanged,
                )
        except (Unreachable, OverBudget) as failed:
            self.status.error = str(failed)
            log.warning("this check stopped: %s", failed)
            return total
        self.status.error = ""
        return total

    # ── Wants ───────────────────────────────────────────────────────────

    def covered(self) -> dict[str, FundState]:
        return {f.instrument_id: f for f in self.status.funds.values() if f.served}

    def _days(self, want: ops.ObservationsWantedEvent) -> list[date]:
        if want.business_date:
            return [date.fromisoformat(want.business_date)]
        today = self.vendor.today() if self.vendor else self.now().astimezone(NEW_YORK).date()
        if want.valid_from_ns or want.valid_until_ns:
            start = datetime.fromtimestamp(want.valid_from_ns // 10**9, NEW_YORK).date()
            end_ns = want.valid_until_ns or _ns(self.now())
            end = datetime.fromtimestamp(end_ns // 10**9, NEW_YORK).date()
            days = [start + timedelta(days=n) for n in range((end - start).days + 1)]
            return [d for d in days if d.weekday() < 5][-MOST_DAYS:]
        return [today - timedelta(days=n) for n in range(LOOKBACK_DAYS, -1, -1)]

    async def _decline(
        self, want_id: str, subjects: Sequence[str], reason: str, declined: dict[str, int]
    ) -> None:
        if not subjects:
            return
        await self.plugin.decline_want(
            want_id=want_id,
            subjects=[ops.SubjectRef(entity_id=s) for s in subjects],
            reason=reason,
        )
        declined[reason] = declined.get(reason, 0) + len(subjects)

    async def on_want(self, heard: meridian.Heard[ops.ObservationsWantedEvent]) -> None:
        """Record what the lake wants of the plugin's dataset, or decline it."""
        want = heard.message
        if want.dataset and want.dataset != self.dataset:
            return
        asked = [s.entity_id for s in want.subjects]
        declined: dict[str, int] = {}
        recorded = 0
        kinds = set(want.kinds)
        price = want.data_type in ("", "meridian.v1.Price")
        if not price or (kinds and ops.PRICE_KIND_NAV not in kinds):
            await self._decline(want.want_id, asked, "not_covered", declined)
            self._answered(want, asked, recorded, declined)
            return
        if not self.covered() and self.vendor is not None:
            # A want before the first check: ask Tiingo about the funds now.
            for fund in list(self.status.funds.values()):
                try:
                    await self.prepare(fund)
                except (Unreachable, OverBudget) as failed:
                    self.status.error = str(failed)
                    break
        covered = self.covered()
        await self._decline(
            want.want_id, [s for s in asked if s not in covered], "not_covered", declined
        )
        mine = [s for s in asked if s in covered]
        if want.standing:
            self.status.standing[want.want_id] = (len(mine), self.now())
        for subject in mine:
            recorded += await self._answer(want, covered[subject], declined)
        self._answered(want, asked, recorded, declined)

    async def _answer(
        self, want: ops.ObservationsWantedEvent, fund: FundState, declined: dict[str, int]
    ) -> int:
        days = self._days(want)
        if fund.start:
            first = date.fromisoformat(fund.start)
            if days and all(d < first for d in days):
                await self._decline(want.want_id, [fund.instrument_id], "beyond_history", declined)
                return 0
            days = [d for d in days if d >= first]
        done = Outcome()
        if days:
            try:
                fetched, key = await self.fetch(prices_path(fund.ticker, min(days), max(days)))
                if fetched.status == 200:
                    done = await self.record(fund, fetched, key, want_id=want.want_id, days=days)
            except (Unreachable, OverBudget) as failed:
                self.status.error = str(failed)
                log.warning("want %s for %s not read: %s", want.want_id, fund.ticker, failed)
        count = done.recorded + done.restated + done.unchanged
        if count == 0:
            await self._decline(want.want_id, [fund.instrument_id], "source_silent", declined)
        return count

    def _answered(
        self,
        want: ops.ObservationsWantedEvent,
        asked: Sequence[str],
        recorded: int,
        declined: dict[str, int],
    ) -> None:
        what = want.business_date or ("a range" if want.valid_from_ns else "the latest")
        self.status.wants.insert(
            0,
            Answered(
                want.want_id,
                what,
                len(asked),
                recorded,
                tuple(sorted(declined.items())),
                self.now(),
                want.standing,
            ),
        )
        del self.status.wants[RECENT:]
        log.info(
            "want %s for %s: %d NAVs recorded, declined %s",
            want.want_id,
            what,
            recorded,
            dict(declined) or "none",
        )

    async def on_withdrawn(self, heard: meridian.Heard[ops.WantWithdrawnEvent]) -> None:
        if heard.message.dataset and heard.message.dataset != self.dataset:
            return
        self.status.standing.pop(heard.message.want_id, None)
        log.info("standing want %s withdrawn", heard.message.want_id)
