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
- the licence Tiingo's free and Power plans give, as the plugin's builders
  read them (README, "The terms"): for internal and personal use, no
  redistribution -- so one person's terms (`personal_use`), kept, used to
  value that person's own book and shown to them. A deployment's licence
  confirms or replaces it on the Data sources page, which warns when more
  than one person may read it; the plugin says nothing of whether a
  deployment meets Tiingo's terms.

**Storage:** Tiingo's responses (raw.py), archivable, two years by default.
"""

from __future__ import annotations

from meridian import DatasetDeclaration, DatasetLicence
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
    licence_default=DatasetLicence(kept=True, derived_use=True, display=True, personal_use=True),
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
