"""The `dgm` suite (meridian.suites, contract v18), each case Tiingo's NAVs
present mapped to the plugin's own conversion of synthetic Tiingo responses.

The plugin serves one thing: mutual funds' net asset values. It presents
five of the suite's twelve cases. Seven ask for what it never records, and it
has no conversion for them, so they have no producer here:

- `a-daily-close`, `the-forming-day-restated` and `an-fx-rate` each expect a
  price of kind `close`; a fund's price is its NAV, kind `nav`, and the
  plugin records no close (Tiingo's closes of stocks and ETFs are the equity
  datasets');
- `a-daily-bar`: a fund's open, high and low are its NAV and its volume 0,
  which is no bar;
- `a-stablecoin-quote`: no crypto asset;
- `a-venue-resolved` and `a-venue-not-held`: a fund strikes its NAV on no
  venue, so the dataset declares none and no row names one.

The SDK's runner lets only a closed-list case be "not presented", and none of
these is one, so by its rule the plugin is short of the suite and not
verified: the test holds it to exactly the five it presents, and to the
seven failing for want of a producer, never for a wrong answer. Whether a
source may say it records no closes, bars, tokens or venues is a question
for the suite's owner (meridian-design matrix/boundaries/suites/dgm.yaml),
raised with this build.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import Recorder, names, run

from tiingo.feed import Feed
from tiingo.raw import RawStore
from tiingo.settings import Config, Fund

from conftest import AT, DATASET, want

NOT_PRESENTED = {
    "a-daily-close": "a fund's price is its NAV, kind nav: no close is recorded",
    "the-forming-day-restated": "a fund's price is its NAV, kind nav: no close is recorded",
    "an-fx-rate": "no currency's rate",
    "a-daily-bar": "a fund's open, high and low are its NAV: no bar",
    "a-stablecoin-quote": "no crypto asset",
    "a-venue-resolved": "a fund strikes its NAV on no venue",
    "a-venue-not-held": "a fund strikes its NAV on no venue",
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
        feed.configure(Config(funds=(Fund("VIGIX"),), synthetic=True))
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
        "a-subject-declined": wanted(want("w-2", ["LCL-elsewhere"], day="2026-10-08").message),
        "a-standing-want-withdrawn": withdrawn,
    }


def test_the_dgm_suite(tmp_path: Path) -> None:
    report = run("dgm", producers(tmp_path), instance_id="tiingo")
    presented = [name for name in names("dgm") if name not in NOT_PRESENTED]
    assert report.passed_cases == presented, report.failures
    assert set(report.failures) == set(NOT_PRESENTED)
    assert all(why.startswith("no producer") for why in report.failures.values()), report.failures


def test_a_nav_never_passes_through_a_float(tmp_path: Path) -> None:
    import asyncio

    recorder = Recorder("tiingo")
    _resolving(recorder)
    feed = Feed(recorder, RawStore(tmp_path), now=lambda: AT)
    feed.configure(Config(funds=(Fund("VIGIX"),), synthetic=True))
    asyncio.run(feed.check())
    amounts = {
        p.meta.row_key: str(as_decimal(p.price.amount))
        for p in recorder.on("RecordPrices")[0].prices
    }
    assert amounts["VIGIX:2026-10-08"] == "245.55"
