"""Shared stand-ins: the synthetic Tiingo, a fixed clock, and the lake's wants
as the sidecar delivers them."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder

from tiingo.feed import Feed
from tiingo.raw import RawStore
from tiingo.settings import Config, Fund

AT = datetime(2026, 10, 10, 11, 0, tzinfo=UTC)
INSTANCE = "tiingo"
DATASET = f"{INSTANCE}:daily"
FUNDS = (Fund("VIGIX"), Fund("VOO"), Fund("NOSUCH"))
#: A custodian's record of VTSAX, as the book holds it: its CUSIP and the
#: custodian's symbol, never resolved by Tiingo.
CUSTODIAN = "LCL-custodian-vtsax"
CUSTODIANS = [
    ops.Identifier(scheme="cusip", value="922908728"),
    ops.Identifier(scheme="symbol", value="VTSAX", source="snaptrade"),
]


def held(recorder: Recorder, records: dict[str, list[ops.Identifier]]) -> None:
    """ResolveInstrument answering the deployment's `records`, by ID; any
    other ID is no record it holds."""

    def answer(params: ops.ResolveInstrumentParams) -> ops.ResolveInstrumentResult:
        identifiers = records.get(params.instrument_id)
        if identifiers is None:
            return ops.ResolveInstrumentResult(found=False)
        return ops.ResolveInstrumentResult(
            found=True,
            instrument=ops.InstrumentRecord(
                instrument_id=params.instrument_id, identifiers=identifiers
            ),
        )

    recorder.answer("ResolveInstrument", answer)


def feed(
    tmp: Path,
    plugin: Recorder | None = None,
    at: datetime = AT,
    funds: tuple[Fund, ...] = FUNDS,
) -> Feed:
    """The plugin's work on the suite's recorder and synthetic Tiingo, at `at`."""
    work = Feed(plugin or Recorder(INSTANCE), RawStore(tmp), now=lambda: at)
    work.configure(Config(funds=funds, synthetic=True))
    return work


def want(
    want_id: str,
    subjects: list[str],
    *,
    day: str = "",
    standing: bool = False,
    kinds: tuple[Any, ...] = (ops.PRICE_KIND_NAV,),
    data_type: str = "meridian.v1.Price",
    dataset: str = DATASET,
) -> Heard:  # type: ignore[type-arg]
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id,
            dataset=dataset,
            data_type=data_type,
            subjects=[ops.SubjectRef(entity_id=s) for s in subjects],
            kinds=list(kinds),
            business_date=day,
            standing=standing,
        ),
    )
