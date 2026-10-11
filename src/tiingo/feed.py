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

**As of now, said** (contract v20, as fed-h10 does): every resolve names its
as-of, the time it is asked -- a fund is resolved once and served for
every day after -- since one left out is the epoch, which no identifier
window the deployment keeps covers. The plugin resolves no currency: a NAV
names its dollars by code, and core resolves the code to the platform
master's currency, pulled, never a stub the plugin minted.

**Records another source named** (W3.6, a data plugin's from contract v18 as ruled
2026-10-10). A record the Funds row names is read: one the deployment does
not hold is not served, and one carrying no Tiingo symbol gains it, reported
beside an identifier it carries (W3.1) -- matching another record is two
records for one fund, reported for a person to merge (W3.2, W3.13). A
subject the lake wants that no listed fund is -- a fund the book holds from
a custodian, known by the custodian's symbol and a CUSIP -- is read the same
way: where it carries a symbol Tiingo files as a mutual fund, and no listed
fund is served under that ticker already, it is served from then on beside
the funds listed, up to the same limit, and Tiingo's symbol joined to it. On
a runtime that grants a data plugin no read of a record, the record a row names is
taken as named and a wanted one declined, as before the ruling.

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
from .settings import MOST_FUNDS, Config, Fund
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
    #: Read from its record when the lake wanted it, not listed in Funds.
    wanted: bool = False

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
    #: Funds served for a record the lake wanted, by that record's ID.
    read: dict[str, FundState] = field(default_factory=dict)
    #: Whether the deployment answers this plugin's ResolveInstrument.
    reads_instruments: bool = True
    #: Subjects declined since start, Tiingo's 429s, and the last time a
    #: NAV was recorded or restated.
    declined: int = 0
    rate_limited: int = 0
    last_recorded_at: datetime | None = None
    #: The datasets a deployment admin has licensed (contract v20), as read.
    licensed: frozenset[str] = frozenset()
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
        #: Wanted records found to be a second record of a fund served,
        #: reported once each.
        self._paired: set[str] = set()

    @property
    def dataset(self) -> str:
        return f"{self.plugin.identity.instance_id}:{DAILY}"

    def configure(self, config: Config) -> None:
        """Take a delivery of the settings: the token and mode, and the funds."""
        keyed = (config.sample_data, config.token)
        if keyed != self._keyed:
            self._keyed = keyed
            self.vendor = tiingo(config.sample_data, config.token, self.now)
            self.status.error = ""
            for fund in self.every_fund():
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
        # A fund listed now is served as its row says, never twice.
        self.status.read = {
            subject: fund
            for subject, fund in self.status.read.items()
            if fund.ticker not in self.status.funds
        }

    def configured(self, funds: Iterable[Fund]) -> None:
        """Set the funds alone, for a test or a preview."""
        self.configure(
            Config(
                token="",
                funds=tuple(funds),
                sample_data=self.vendor is not None and self.vendor.mode == "synthetic",
            )
        )

    def every_fund(self) -> list[FundState]:
        """The funds listed, then those read for a want."""
        return [*self.status.funds.values(), *self.status.read.values()]

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
            self.status.rate_limited += 1
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
            read = await self.read_record(fund.configured)
            if read is not None and not read.found:
                fund.miss = "record_not_found"
                return
            fund.instrument_id, fund.miss = fund.configured, ""
            if read is not None:
                await self.join(fund, read.instrument)
            return
        identifier = ops.Identifier(scheme="symbol", value=fund.ticker, source=SOURCE)
        found = await self.plugin.resolve_identifier(
            identifiers=[identifier],
            as_of_ns=_ns(self.now()),
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
            as_of_ns=_ns(self.now()),
            observed_at_ns=_ns(self.now()),
        )

    # ── The deployment's records (W3.6, W3.1, W3.2) ─────────────────────

    async def read_record(self, instrument_id: str) -> ops.ResolveInstrumentResult | None:
        """What the deployment's record is; None where this data plugin may not read
        it, on a runtime from before the ruling of 2026-10-10 (asked once)."""
        if not self.status.reads_instruments:
            return None
        try:
            found: ops.ResolveInstrumentResult = await self.plugin.resolve_instrument(
                instrument_id=instrument_id, as_of_ns=_ns(self.now())
            )
        except meridian.NotGranted:
            log.warning(
                "this data plugin may not read an instrument's record: serving the funds listed"
            )
            self.status.reads_instruments = False
            return None
        return found

    async def join(self, fund: FundState, record: ops.InstrumentRecord) -> None:
        """Report Tiingo's symbol beside an identifier the record carries
        (W3.1), where it carries none of Tiingo's: one identifier in common
        is one security, so the record gains Tiingo's code. Matching another
        record, or none, is a miss (W3.2), and the record stays the subject."""
        held = list(record.identifiers)
        if any(i.scheme == "symbol" and i.source == SOURCE for i in held):
            return
        symbols = [i for i in held if i.scheme == "symbol" and i.value.upper() == fund.ticker]
        given = (symbols or held or [None])[0]
        if given is None:
            return
        own = ops.Identifier(scheme="symbol", value=fund.ticker, source=SOURCE)
        given = ops.Identifier(scheme=given.scheme, value=given.value, source=given.source)
        found = await self.plugin.resolve_identifier(
            identifiers=[own, given],
            as_of_ns=_ns(self.now()),
            stated_asset_class="fund",
            stated_currency="USD",
            stated_description=fund.name,
        )
        if found.found and found.instrument_id == fund.instrument_id:
            return
        reason = ops.MISS_REASON_AMBIGUOUS
        if not found.found and found.miss_reason:
            reason = found.miss_reason
        await self.plugin.report_missing_instrument(
            source=SOURCE,
            asset_class="fund",
            identifiers=[own, given],
            reason=reason,
            as_of_ns=_ns(self.now()),
            observed_at_ns=_ns(self.now()),
        )

    async def read_wanted(self, subject: str) -> FundState | None:
        """The fund a wanted subject no listed fund is, read from its record:
        served where its symbol is a mutual fund at Tiingo that no fund is
        served under already; None where it is not one, or not readable."""
        held = self.status.read.get(subject)
        if held is not None:
            return held if held.served else None
        if subject in self._paired:
            return None
        if len(self.status.funds) + len(self.status.read) >= MOST_FUNDS:
            return None
        read = await self.read_record(subject)
        if read is None or not read.found:
            return None
        symbols = [i for i in read.instrument.identifiers if i.scheme == "symbol" and i.value]
        symbols.sort(key=lambda i: i.source != SOURCE)
        if not symbols:
            return None
        fund = FundState(symbols[0].value.strip().upper(), instrument_id=subject, wanted=True)
        if any(f.ticker == fund.ticker and f.served for f in self.every_fund()):
            # Two records for one fund: Tiingo's symbol joined to this one
            # reports the pair for a person to merge (W3.13); its rows stay
            # under the record that is served, never keyed twice.
            self._paired.add(subject)
            await self.join(fund, read.instrument)
            return None
        await self.meta(fund)
        self.status.read[subject] = fund
        if not fund.served:
            return None
        await self.join(fund, read.instrument)
        return fund

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
        if outcome.recorded or outcome.restated:
            self.status.last_recorded_at = self.now()
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
            for fund in self.every_fund():
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
        return {f.instrument_id: f for f in self.every_fund() if f.served}

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
        self.status.declined += len(subjects)

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
        for subject in [s for s in dict.fromkeys(asked) if s not in covered]:
            try:
                found = await self.read_wanted(subject)
            except (Unreachable, OverBudget) as failed:
                self.status.error = str(failed)
                break
            if found is not None:
                covered[subject] = found
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
