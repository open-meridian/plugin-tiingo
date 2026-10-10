"""The plugin's work on its typed operations: funds asked about, resolved or
reported, NAVs pushed, wants recorded against or declined."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder

from tiingo.settings import Config, Fund

from conftest import AT, feed, want


async def test_only_a_mutual_fund_is_served(tmp_path: Path) -> None:
    work = feed(tmp_path)
    done = await work.check()
    assert done is not None and done.recorded == 8  # VIGIX's last ten days: 8 business days
    funds = work.status.funds
    assert funds["VIGIX"].served and funds["VIGIX"].name.startswith("Vanguard Growth")
    assert funds["VOO"].found == "found" and not funds["VOO"].served
    assert funds["NOSUCH"].found == "not_found"
    [resolved] = work.plugin.on("ResolveIdentifier")
    assert resolved.identifiers[0].scheme == "symbol" and resolved.identifiers[0].value == "VIGIX"
    assert resolved.identifiers[0].source == "tiingo"
    [batch] = work.plugin.on("RecordPrices")
    keys = [p.meta.row_key for p in batch.prices]
    assert keys[0] == "VIGIX:2026-09-30" and keys[-1] == "VIGIX:2026-10-09"
    assert {p.kind for p in batch.prices} == {ops.PRICE_KIND_NAV}
    assert funds["VIGIX"].latest == "2026-10-09"


async def test_a_record_the_setting_names_is_the_subject(tmp_path: Path) -> None:
    work = feed(tmp_path, funds=(Fund("VIGIX", "LCL-from-snaptrade"),))
    await work.check()
    assert not work.plugin.on("ResolveIdentifier")
    [batch] = work.plugin.on("RecordPrices")
    assert {p.meta.subjects[0].entity_id for p in batch.prices} == {"LCL-from-snaptrade"}


async def test_a_nav_read_again_names_the_response_first_read(tmp_path: Path) -> None:
    first = feed(tmp_path)
    await first.check()
    again = feed(tmp_path, at=AT + timedelta(hours=6))
    await again.check()
    keys = [{p.meta.raw.key for p in w.plugin.on("RecordPrices")[0].prices} for w in (first, again)]
    assert keys[0] == keys[1] and len(keys[0]) == 1


async def test_a_fund_that_resolves_to_two_records_is_reported(tmp_path: Path) -> None:
    recorder = Recorder("tiingo")
    recorder.answer(
        "ResolveIdentifier",
        lambda _: ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_AMBIGUOUS),
    )
    work = feed(tmp_path, recorder)
    await work.check()
    [missed] = recorder.on("ReportMissingInstrument")
    assert missed.reason == ops.MISS_REASON_AMBIGUOUS and missed.source == "tiingo"
    assert work.status.funds["VIGIX"].miss == "ambiguous"
    assert not recorder.on("RecordPrices")


async def test_a_past_day_wanted_is_recorded_against_the_want(tmp_path: Path) -> None:
    work = feed(tmp_path)
    await work.check()
    vigix = work.status.funds["VIGIX"].instrument_id
    await work.on_want(want("w-1", [vigix], day="2026-09-22"))
    batch = work.plugin.on("RecordPrices")[-1]
    assert batch.want_id == "w-1" and [p.meta.row_key for p in batch.prices] == ["VIGIX:2026-09-22"]


async def test_a_want_before_the_first_check(tmp_path: Path) -> None:
    recorder = Recorder("tiingo")
    recorder.answer(
        "ResolveIdentifier",
        lambda _: ops.ResolveIdentifierResult(found=True, instrument_id="LCL-VIGIX"),
    )
    work = feed(tmp_path, recorder)
    await work.on_want(want("w-0", ["LCL-VIGIX"], day="2026-10-08"))
    assert recorder.on("RecordPrices")[-1].want_id == "w-0"


async def test_declined_not_covered_silent_and_beyond_history(tmp_path: Path) -> None:
    work = feed(tmp_path)
    await work.check()
    vigix = work.status.funds["VIGIX"].instrument_id
    await work.on_want(want("w-2", ["LCL-elsewhere"], day="2026-10-08"))
    await work.on_want(want("w-3", [vigix], day="2026-10-12"))
    await work.on_want(want("w-4", [vigix], day="1990-01-02"))
    await work.on_want(want("w-5", [vigix], day="2026-10-08", kinds=(ops.PRICE_KIND_CLOSE,)))
    reasons = [(d.want_id, d.reason) for d in work.plugin.on("DeclineWant")]
    assert reasons == [
        ("w-2", ops.UNANSWERED_REASON_NOT_COVERED),
        ("w-3", ops.UNANSWERED_REASON_SOURCE_SILENT),
        ("w-4", ops.UNANSWERED_REASON_BEYOND_HISTORY),
        ("w-5", ops.UNANSWERED_REASON_NOT_COVERED),
    ]


async def test_a_standing_want_is_kept_until_withdrawn(tmp_path: Path) -> None:
    work = feed(tmp_path)
    await work.check()
    vigix = work.status.funds["VIGIX"].instrument_id
    await work.on_want(want("w-6", [vigix], standing=True))
    assert "w-6" in work.status.standing
    await work.on_withdrawn(
        Heard(
            row="WantWithdrawn",
            message=ops.WantWithdrawnEvent(want_id="w-6", dataset="tiingo:daily"),
        )
    )
    assert "w-6" not in work.status.standing


async def test_no_token_reads_nothing(tmp_path: Path) -> None:
    work = feed(tmp_path)
    work.configure(Config(funds=(Fund("VIGIX"),), synthetic=False, missing=("tiingo_api_token",)))
    assert work.vendor is None and work.status.mode == "waiting"
    assert await work.check() is None
    assert not work.plugin.on("RecordPrices")


async def test_a_refused_token_is_said_never_shown(tmp_path: Path) -> None:
    from tiingo.vendor import Budget, Fetched

    class Refusing:
        mode = "live"
        budget = Budget()

        async def get(self, path: str) -> Fetched:
            return Fetched(path, 401, b'{"detail":"Invalid token."}', AT)

        def today(self) -> date:
            return AT.date()

    work = feed(tmp_path)
    work.configure(Config(token="abc123secret", funds=(Fund("VIGIX"),)))
    work.vendor = Refusing()
    await work.check()
    assert "refused the token" in work.status.error and "abc123secret" not in work.status.error
    kept = work.raw.keys()
    assert not any("abc123secret" in (work.raw.read(k) or {}).get("body", "") for k in kept)
