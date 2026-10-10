"""The pages as synthetic mode shows them, each printed as one HTML file:
for looking at them without a deployment.

    python -m tiingo.preview connection > preview/connection.html
    python -m tiingo.preview datasets > preview/datasets.html

The plugin's work runs on the SDK's suite recorder in place of a sidecar,
against the synthetic responses committed under synthetic/ (every value
invented), at 11:00 UTC on 10 October 2026, with three funds listed: VIGIX,
a mutual fund, resolved and its last days recorded; VOO, an ETF, not served;
NOSUCH, which Tiingo does not know. A want for 22 September is answered, one
for 12 October declined (no NAV yet), and a standing want kept current; and
VTSAX, listed nowhere, wanted by a custodian's record (its CUSIP and the
custodian's symbol), read from it and served.
Each page links the kit where the dashboard serves it: served beside the kit
it is styled (`make preview SHOTS=...` checks each in a browser); opened on
its own it is the page without the kit, unstyled, which works too.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder
from meridian.testing import PageClient

from .feed import Feed
from .page import CONNECTION, DATASETS, hold, pages
from .raw import RawStore
from .settings import Config, Fund

AT = datetime(2026, 10, 10, 11, 0, tzinfo=UTC)
PAGES = {"connection": CONNECTION, "datasets": DATASETS, "datasets-search": DATASETS}
#: What the Datasets tab's search is shown with, as `datasets-search`.
SEARCHED = "vanguard"
FUNDS = (Fund("VIGIX"), Fund("VOO"), Fund("NOSUCH"))
#: A custodian's record of VTSAX, which no Funds row lists.
CUSTODIAN = "LCL-custodian-vtsax"


def _want(want_id: str, subject: str, day: str = "", standing: bool = False) -> Heard:  # type: ignore[type-arg]
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id,
            dataset="tiingo:daily",
            data_type="meridian.v1.Price",
            subjects=[ops.SubjectRef(entity_id=subject)],
            kinds=[ops.PRICE_KIND_NAV],
            business_date=day,
            standing=standing,
        ),
    )


async def synthetic_feed() -> Feed:
    """A feed as synthetic mode leaves it, on the recorder."""
    recorder = Recorder("tiingo")
    custodians = [
        ops.Identifier(scheme="cusip", value="922908728"),
        ops.Identifier(scheme="symbol", value="VTSAX", source="snaptrade"),
    ]
    recorder.answer(
        "ResolveInstrument",
        lambda p: ops.ResolveInstrumentResult(
            found=p.instrument_id == CUSTODIAN,
            instrument=ops.InstrumentRecord(instrument_id=CUSTODIAN, identifiers=custodians),
        ),
    )
    recorder.answer(
        "ResolveIdentifier",
        lambda p: ops.ResolveIdentifierResult(
            found=True,
            instrument_id=CUSTODIAN if len(p.identifiers) == 2 else f"LCL-{p.identifiers[0].value}",
        ),
    )
    feed = Feed(recorder, RawStore(), now=lambda: AT)
    feed.configure(Config(funds=FUNDS, synthetic=True))
    await feed.check()
    vigix = feed.status.funds["VIGIX"].instrument_id
    await feed.on_want(_want("want-0922", vigix, "2026-09-22"))
    await feed.on_want(_want("want-1012", vigix, "2026-10-12"))
    await feed.on_want(_want("want-standing", vigix, standing=True))
    await feed.on_want(_want("want-vtsax", CUSTODIAN, "2026-10-08"))
    return feed


def render(page: str) -> str:
    feed = asyncio.run(synthetic_feed())
    hold(feed)
    query = {"q": SEARCHED} if page == "datasets-search" else {}
    answer = PageClient(pages).get(PAGES[page], "admin", **query)
    if answer.status != 200:
        raise SystemExit(f"{page} answered {answer.status}: {answer.text[:200]}")
    return answer.text


def main() -> None:
    page = sys.argv[1] if len(sys.argv) > 1 else "connection"
    if page not in PAGES:
        raise SystemExit(f"no page {page!r}: {', '.join(PAGES)}")
    sys.stdout.write(render(page))


if __name__ == "__main__":
    main()
