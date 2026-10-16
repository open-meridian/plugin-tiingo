"""The data suite (meridian.suites, contract v20), each case Tiingo's NAVs
present mapped to the plugin's own conversion of recorded Tiingo responses,
the whole suite passing.

The plugin serves one thing: mutual funds' net asset values, kind `nav`. A
case about a kind of data it never publishes (`about`, from contract v19)
is not presented, with why (`NOT_PRESENTED`): closes (a fund's price is its
NAV), bars, a currency's rate, a crypto asset's price, prices on a venue (a
fund strikes its NAV on no venue), trades and quotes. A case about a field
of a trade (`about_field`, from contract v20) is about trades, so not
presented the same way; and so is a restart's gap, backfilled, which is
about trades. Contract v22's calendar cases (`about` calendars and
settlement dates) are not presented either: the plugin records each NAV on
the business date Tiingo states, and never reads a settlement calendar or
asks for a settlement date; nor are contract v23's outcomes (no event
contract). Every other case is presented, its datasets' licences among them,
and contract v24's two every-role cases are the SDK's.

`a-subject-another-source-resolved` (contract v18 as ruled 2026-10-10) is
presented: a fund the book holds from a custodian, its record carrying the
custodian's symbol and a CUSIP, is read (W3.6) and its NAV recorded against
the want.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import Recorder, run, suite

from tiingo.feed import Feed
from tiingo.raw import RawStore
from tiingo.settings import Config, Fund

from conftest import AT, CUSTODIAN, CUSTODIANS, DATASET, held, want

#: Why each kind of data a case may be about is never published here.
NEVER = {
    "closes": "a fund's price is its NAV, kind nav: no close is recorded",
    "bars": "a fund's open, high and low are its NAV: no bar",
    "a currency's rate against another currency": "no currency's rate",
    "a crypto asset's price": "no crypto asset",
    "prices on a venue": "a fund strikes its NAV on no venue",
    "trades": "mutual funds' NAVs only: Tiingo's end-of-day prices state no trades",
    "quotes": "mutual funds' NAVs only: Tiingo's end-of-day prices state no quotes",
    "calendars": (
        "records each NAV on the business date Tiingo states: reads no settlement calendar"
    ),
    "settlement dates": "records NAVs as published; never computes a settlement date",
    # Contract v23: an event contract's outcome.
    "outcomes": "mutual funds' NAVs only: no event contract, so no outcome",
    "disputed outcomes": "mutual funds' NAVs only: no event contract, so no outcome",
}

NOT_PRESENTED = {
    case.name: NEVER[case.about] for case in suite("data").cases if case.about in NEVER
}


def _resolving(recorder: Recorder, ambiguous: bool = False) -> None:
    def answer(params: ops.ResolveIdentifierParams) -> ops.ResolveIdentifierResult:
        if ambiguous:
            return ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_AMBIGUOUS)
        return ops.ResolveIdentifierResult(
            found=True, instrument_id=f"LCL-{params.identifiers[0].value}"
        )

    recorder.answer("ResolveIdentifier", answer)


def producers(tmp: Path) -> dict[str, Callable[[Recorder], Awaitable[None]]]:
    def work(recorder: Recorder) -> Feed:
        feed = Feed(recorder, RawStore(tmp), now=lambda: AT)
        feed.configure(Config(funds=(Fund("VIGIX"),), sample_data=True))
        return feed

    async def navs_read(recorder: Recorder) -> None:
        _resolving(recorder)
        await work(recorder).check()

    async def two_records(recorder: Recorder) -> None:
        _resolving(recorder, ambiguous=True)
        await work(recorder).check()

    def wanted(message: Any) -> Callable[[Recorder], Awaitable[None]]:
        async def produce(recorder: Recorder) -> None:
            _resolving(recorder)
            feed = work(recorder)
            recorder.answer("ObservationsWanted", lambda _: message)
            await recorder.receive(observations_wanted=feed.on_want)

        return produce

    async def elsewhere(recorder: Recorder) -> None:
        # VTSAX as a custodian's book holds it, by its CUSIP and the
        # custodian's symbol: the record read, Tiingo's symbol joined to it.
        held(recorder, {CUSTODIAN: CUSTODIANS})
        recorder.answer(
            "ResolveIdentifier",
            lambda p: ops.ResolveIdentifierResult(
                found=True,
                instrument_id=CUSTODIAN
                if any(i.value == "VTSAX" for i in p.identifiers)
                else "LCL-VIGIX",
            ),
        )
        feed = work(recorder)
        message = want("w-3", [CUSTODIAN], day="2026-10-08").message
        recorder.answer("ObservationsWanted", lambda _: message)
        await recorder.receive(observations_wanted=feed.on_want)

    async def licences(recorder: Recorder) -> None:
        # On start, its own declared datasets' licences (contract v20).
        from tiingo.__main__ import read_licences

        recorder.answer(
            "ListDatasets",
            lambda _: ops.ListDatasetsResult(licences=[ops.DatasetLicence(dataset=DATASET)]),
        )
        feed = work(recorder)
        await read_licences(recorder, feed)
        assert feed.status.licensed == {DATASET}

    async def withdrawn(recorder: Recorder) -> None:
        _resolving(recorder)
        feed = work(recorder)
        recorder.answer(
            "WantWithdrawn", lambda _: ops.WantWithdrawnEvent(want_id="w-standing", dataset=DATASET)
        )
        await recorder.receive(want_withdrawn=feed.on_withdrawn)

    return {
        "an-exact-price": navs_read,
        "an-asset-that-does-not-resolve": two_records,
        "a-want-recorded-against": wanted(want("w-1", ["LCL-VIGIX"], day="2026-09-22").message),
        "a-subject-another-source-resolved": elsewhere,
        "a-subject-declined": wanted(want("w-2", ["LCL-elsewhere"], day="2026-10-08").message),
        "a-standing-want-withdrawn": withdrawn,
        "reads-its-datasets-licences": licences,
    }


def test_the_data_suite_passes(tmp_path: Path) -> None:
    report = run("data", producers(tmp_path), not_presented=NOT_PRESENTED, instance_id="tiingo")
    assert report.passed, report.failures
    assert sorted(report.not_presented) == sorted(NOT_PRESENTED)
    # Contract v24: the two cases every suite holds, which the SDK answers.
    assert len(report.passed_cases) == 9
    assert report.answered_by_sdk == [
        "hears-and-reads-a-replacement",
        "reads-the-template-catalogue",
    ]


def test_a_nav_never_passes_through_a_float(tmp_path: Path) -> None:
    import asyncio

    recorder = Recorder("tiingo")
    _resolving(recorder)
    feed = Feed(recorder, RawStore(tmp_path), now=lambda: AT)
    feed.configure(Config(funds=(Fund("VIGIX"),), sample_data=True))
    asyncio.run(feed.check())
    amounts = {
        p.meta.row_key: str(as_decimal(p.price.amount))
        for p in recorder.on("RecordPrices")[0].prices
    }
    assert amounts["VIGIX:2026-10-08"] == "245.55"


def test_the_daily_dataset_names_the_us_equity_calendar() -> None:
    """v24 (the plan's O10): the NAVs' business dates follow the platform's
    US equity venues (NYSE markets) calendar."""
    from tiingo.declared import DAILY_DATASET, US_EQUITY_CALENDAR

    assert US_EQUITY_CALENDAR == "CAL-01M4VF0F4XGP3RATCCSKDPZSBP"
    assert DAILY_DATASET.calendar_id == US_EQUITY_CALENDAR
    assert DAILY_DATASET._to_json()["calendar_id"] == US_EQUITY_CALENDAR
