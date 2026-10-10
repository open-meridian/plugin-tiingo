"""The plugin's settings, declared to the SDK, and what it makes of them.

- **API token** (`tiingo_api_token`), secret and required: the token of the
  person's own Tiingo account, from its API page. Entered by that person in
  the dashboard's Settings form, sent only to Tiingo, in a header; never
  logged, shown, kept or put in an address. Its name follows the retail
  plugins' (`alpaca_api_key_id`): the vendor's, then what it is.
- **Funds** (`funds`), a table: each mutual fund to keep NAVs for, by its
  ticker (`VIGIX`), and, where its ticker alone does not find it, the
  deployment's own record for it (an instrument column, picked by search):
  the record the custodian's positions already name, say.
- **Synthetic mode** (`synthetic`), a developer's setting, SnapTrade's name
  for the same thing: synthetic responses committed with the plugin in place
  of Tiingo, with no token, for the e2e and for trying the plugin.

The SDK declares the storage's two settings from the declaration's kind:
`responses_window_days` (two years by default) and `responses_past_window`.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field

import meridian

from .raw import DEFAULT_WINDOW_DAYS, RESPONSES

TOKEN = "tiingo_api_token"
FUNDS = "funds"
TICKER = "ticker"
INSTRUMENT = "instrument"
SYNTHETIC = "synthetic"
WINDOW = f"{RESPONSES}_window_days"
PAST_WINDOW = f"{RESPONSES}_past_window"
#: The most funds: a fifth of the free plan's 500 symbols a month.
MOST_FUNDS = 100

DECLARED = (
    meridian.Setting(
        TOKEN,
        str,
        required=True,
        secret=True,
        label="API token",
        description=(
            "From your Tiingo account's API page. Tiingo's free plan suffices for a few "
            "funds' daily NAVs; its terms are for your internal and personal use."
        ),
    ),
    meridian.Setting(
        FUNDS,
        list,
        label="Funds",
        columns=(
            meridian.Column(
                TICKER,
                label="Ticker",
                required=True,
                description="The mutual fund's ticker, as Tiingo knows it, such as VIGIX.",
            ),
            meridian.Column(
                INSTRUMENT,
                "instrument",
                label="Instrument",
                description=(
                    "Optional: this deployment's record for the fund, where its ticker alone "
                    "does not find it, such as the one your custodian's positions name."
                ),
            ),
        ),
        most_rows=MOST_FUNDS,
        description="The mutual funds to keep daily net asset values for.",
    ),
    meridian.Setting(
        SYNTHETIC,
        bool,
        label="Synthetic mode",
        default=False,
        developer=True,
        description=(
            "Serve synthetic Tiingo responses committed with the plugin, every value "
            "invented, instead of calling Tiingo, to try it before any token exists."
        ),
    ),
)


@dataclass(frozen=True)
class Fund:
    """One row of the Funds table."""

    ticker: str
    instrument_id: str = ""


@dataclass(frozen=True)
class Config:
    token: str = field(default="", repr=False)
    funds: tuple[Fund, ...] = ()
    synthetic: bool = False
    window_days: int = DEFAULT_WINDOW_DAYS
    past_window: str = "kept"
    missing: tuple[str, ...] = ()

    @property
    def waiting(self) -> bool:
        """Whether there is nothing to read with: no token, and not synthetic."""
        return not self.synthetic and not self.token


def config_from(values: Mapping[str, object], missing: Collection[str] = ()) -> Config:
    """The configuration a delivery of the settings says."""
    token = values.get(TOKEN)
    rows = values.get(FUNDS)
    funds: dict[str, Fund] = {}
    for row in rows if isinstance(rows, list) else []:
        ticker = str(row.get(TICKER, "")).strip().upper() if isinstance(row, dict) else ""
        if ticker and ticker not in funds:
            funds[ticker] = Fund(ticker, str(row.get(INSTRUMENT, "") or "").strip())
    window = values.get(WINDOW)
    past = values.get(PAST_WINDOW)
    return Config(
        token=token.strip() if isinstance(token, str) else "",
        funds=tuple(funds.values()),
        synthetic=values.get(SYNTHETIC) is True,
        window_days=window if isinstance(window, int) and window > 0 else DEFAULT_WINDOW_DAYS,
        past_window=past if isinstance(past, str) and past else "kept",
        missing=tuple(sorted(missing)),
    )
