"""What this version declares beside its role (W8.1, W4.1; the catalogue from
contract v18), built from code and used twice: `__main__` registers with it,
and `meridian plugin upload` reads it from the built image
(pyproject.toml's `[tool.meridian] declaration`).

**The catalogue: one dataset, `daily`** (the plan's Q21: a daily dataset per
plugin; Tiingo's NAVs come once a day). Mutual funds' net asset values, end
of day:

- `vendor` Tiingo, which collects them; no aggregator named, since Tiingo is
  the source the plugin reads;
- `data_types` prices alone, of kind `nav` (convert.py);
- `modes` `push` (each fund's latest NAVs recorded as Tiingo has them, after
  midnight New York time) and `pull` (a past day, on a want);
- `cadence` a day, in seconds;
- `history` none stated: each fund's history starts where Tiingo's meta says,
  shown per fund on the Datasets tab;
- its day New York's, ending at 16:00 (`America/New_York`, 960), when a fund
  strikes its NAV; its business dates the platform's US equity venues (NYSE
  markets) calendar's (`calendar_id`, from 0.5.0);
- no venue: a fund's NAV is struck by the fund, on no venue;
- its declared delay (contract v27, `declared_delay_ns`) eight hours: a
  fund strikes its NAV at the day's end, 16:00 New York, and Tiingo serves
  it from midnight ("Mutual Fund NAVs are available after 12 AM EST",
  Tiingo's end-of-day documentation), so the lake judges a NAV's staleness
  against the delay plus its ceiling, never as late from 16:00;
- its terms and pricing in plain words (contract 30, ruling 1032;
  `terms_and_pricing`), as the plugin's builders read Tiingo's (README,
  "The terms"): the free and Power plans for internal and personal use, no
  redistribution, and the free plan's limits. Never a licence: the
  deployment admin's licence on the Data sources page is the one enforced,
  and the plugin says nothing of whether a deployment meets Tiingo's terms;
- a gap recovered by `backfill` (contract 30, `gap_recovery`): Tiingo serves
  each fund's history, so the lake asks for the days again.

**Storage:** Tiingo's responses (raw.py), archivable, two years by default.
"""

from __future__ import annotations

from meridian import DatasetDeclaration
from meridian.declaration import RecordKind
from meridian.plugin.v1 import operations_pb2 as ops

from .convert import DAY_END_MINUTE, DAY_TIME_ZONE
from .raw import DEFAULT_WINDOW_DAYS, RESPONSES

#: The dataset's key: its rows name `<instance>:daily`.
DAILY = "daily"
VENDOR = "Tiingo"
#: The platform's "US equity venues (NYSE markets)" trading calendar, read from
#: the platform on 2026-10-14 (the v24 plan's O10): a fund strikes its NAV on
#: the days US equity markets are open, so the lake flags a NAV dated on a
#: closed day.
US_EQUITY_CALENDAR = "CAL-01M4VF0F4XGP3RATCCSKDPZSBP"
#: Tiingo's terms and pricing in plain words (contract 30, ruling 1032), as
#: the plugin's builders read them on tiingo.com.
TERMS = (
    "Tiingo collects mutual funds' net asset values and serves them through its API "
    "under the account holder's own agreement. Its free and Power plans are for internal "
    "and personal use, with no redistribution; a firm's use or redistribution needs "
    "Tiingo's commercial terms. The free plan allows 50 requests an hour, 1,000 a day and "
    "500 symbols a month; Power and commercial plans are paid, at the prices on "
    "tiingo.com. NAVs arrive after midnight New York time."
)
#: A day, in seconds.
CADENCE = 86_400
#: How far behind the day's end Tiingo serves a fund's NAV: from 16:00 New
#: York, when the fund strikes it, to midnight, when Tiingo has it.
DECLARED_DELAY_NS = (24 * 60 - DAY_END_MINUTE) * 60 * 1_000_000_000

DAILY_DATASET = DatasetDeclaration(
    key=DAILY,
    vendor=VENDOR,
    data_types=["meridian.v1.Price"],
    modes=["push", "pull"],
    cadence=CADENCE,
    terms_and_pricing=TERMS,
    gap_recovery="backfill",
    day_time_zone=DAY_TIME_ZONE,
    day_end_minute=DAY_END_MINUTE,
    calendar_id=US_EQUITY_CALENDAR,
    declared_delay_ns=DECLARED_DELAY_NS,
)

RESPONSES_KIND = RecordKind(RESPONSES, "Raw responses", window_days=DEFAULT_WINDOW_DAYS)


def mode_name(mode: int | str) -> str:
    """A mode as the catalogue's words say it (`push`), however it is held."""
    if isinstance(mode, str):
        return mode
    return str(ops.ObservationMode.Name(mode)).removeprefix("OBSERVATION_MODE_").lower()
