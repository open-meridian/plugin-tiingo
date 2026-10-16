"""Each fund's ticker mapped to its FIGIs through OpenFIGI under the
deployment's access (figi.py, decision 64), and stated on its resolve so it
meets the platform's record. OpenFIGI is never called here: a fake stands in
for its answers, and the live client's request is read, never sent."""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import Recorder

from tiingo.figi import Figis, LiveOpenFigi, Unmapped, figis_of, jobs
from tiingo.settings import Config, Fund, config_from

from conftest import feed


class Fake:
    """OpenFIGI's answers, by ticker; refused where told to be."""

    mode = "fake"

    def __init__(self, answers: dict[str, Figis | None], refused: bool = False) -> None:
        self.answers = answers
        self.refused = refused
        self.asked: list[list[str]] = []

    async def map(self, tickers: Sequence[str]) -> dict[str, Figis | None]:
        self.asked.append(list(tickers))
        if self.refused:
            raise Unmapped("OpenFIGI answered 429")
        return {ticker: self.answers.get(ticker) for ticker in tickers}


def schemes(params: Any) -> list[tuple[str, str, str]]:
    return [(i.scheme, i.value, i.source) for i in params.identifiers]


async def test_the_resolve_states_each_figi_beside_tiingos_symbol(tmp_path: Path) -> None:
    work = feed(tmp_path, funds=(Fund("VIGIX"),))
    fake = Fake({"VIGIX": Figis("BBG000XVIGX1", "BBG000XVIGX2", "BBG001SVIGX3")})
    work.figi = fake
    await work.check()
    [resolved] = work.plugin.on("ResolveIdentifier")
    assert schemes(resolved) == [
        ("symbol", "VIGIX", "tiingo"),
        ("figi", "BBG000XVIGX1", ""),
        ("composite_figi", "BBG000XVIGX2", ""),
        ("share_class_figi", "BBG001SVIGX3", ""),
    ]
    assert fake.asked == [["VIGIX"]]
    await work.check()
    assert fake.asked == [["VIGIX"]], "each ticker mapped once"


async def test_sample_data_maps_by_the_invented_figis(tmp_path: Path) -> None:
    """Sample data never calls OpenFIGI: VIGIX by the FIGI the e2e's stand-in
    platform holds."""
    work = feed(tmp_path, funds=(Fund("VIGIX"),))
    assert work.figi is not None and work.figi.mode == "synthetic"
    await work.check()
    [resolved] = work.plugin.on("ResolveIdentifier")
    assert ("figi", "BBG00E2EVIGX", "") in schemes(resolved)


async def test_none_found_resolves_by_tiingos_symbol_alone(tmp_path: Path) -> None:
    work = feed(tmp_path, funds=(Fund("VIGIX"),))
    work.figi = Fake({})
    await work.check()
    [resolved] = work.plugin.on("ResolveIdentifier")
    assert schemes(resolved) == [("symbol", "VIGIX", "tiingo")]
    assert work.status.funds["VIGIX"].figi_asked


async def test_openfigi_refusing_is_said_and_asked_again(tmp_path: Path) -> None:
    recorder = Recorder("tiingo")
    recorder.answer(
        "ResolveIdentifier",
        lambda _: ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_NOT_FOUND),
    )
    work = feed(tmp_path, recorder, funds=(Fund("VIGIX"),))
    fake = Fake({"VIGIX": Figis("BBG000XVIGX1")}, refused=True)
    work.figi = fake
    await work.check()
    assert work.status.figi_error == "OpenFIGI answered 429"
    assert not work.status.funds["VIGIX"].figi_asked
    fake.refused = False
    await work.check()
    assert work.status.figi_error == ""
    assert ("figi", "BBG000XVIGX1", "") in schemes(recorder.on("ResolveIdentifier")[-1])


def test_more_than_one_figi_is_never_guessed_between() -> None:
    assert figis_of({"warning": "No identifier found."}) is None
    assert figis_of({"data": [{"figi": "A"}, {"figi": "B"}]}) is None
    assert figis_of({"data": [{"figi": "A", "shareClassFIGI": "S"}, {"figi": "A"}]}) == Figis(
        "A", "", "S"
    )


def test_a_job_asks_for_a_us_mutual_fund_by_its_ticker() -> None:
    assert jobs(["VIGIX"]) == [
        {"idType": "TICKER", "idValue": "VIGIX", "exchCode": "US", "securityType2": "Mutual Fund"}
    ]


def test_the_deployments_key_is_sent_in_its_header_and_nowhere_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[Any] = []

    class Answer:
        def __enter__(self) -> Answer:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self, _limit: int) -> bytes:
            return json.dumps([{"data": [{"figi": "BBG000XVIGX1"}]}]).encode()

    def urlopen(request: Any, timeout: float) -> Answer:
        sent.append(request)
        return Answer()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    LiveOpenFigi("the-key")._send(jobs(["VIGIX"]))
    LiveOpenFigi()._send(jobs(["VIGIX"]))
    keyed, keyless = sent
    assert keyed.get_header("X-openfigi-apikey") == "the-key"
    assert keyless.get_header("X-openfigi-apikey") is None
    assert "the-key" not in keyed.full_url and b"the-key" not in keyed.data


async def test_batches_keep_to_the_keyless_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    posted: list[int] = []

    async def post(self: LiveOpenFigi, body: list[dict[str, str]]) -> Any:
        posted.append(len(body))
        return [{"warning": "No identifier found."} for _ in body]

    monkeypatch.setattr(LiveOpenFigi, "_post", post)
    tickers = [f"T{n:02d}" for n in range(23)]
    assert set((await LiveOpenFigi().map(tickers)).values()) == {None}
    assert posted == [10, 10, 3]
    posted.clear()
    await LiveOpenFigi("key").map(tickers)
    assert posted == [23]


def test_the_key_is_an_optional_secret_setting() -> None:
    assert config_from({"openfigi_api_key": " k "}).openfigi_key == "k"
    assert config_from({}).openfigi_key == ""
    assert "the-key" not in repr(Config(openfigi_key="the-key"))
