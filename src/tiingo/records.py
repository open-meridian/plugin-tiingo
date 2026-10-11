"""The typed records the pages answer, for a person's page and an agent's
tool alike (contract v12; spec/a-deployment-serves-its-mcp): the data role's
common records (`meridian.roles.data`, spec/plugin-pages-follow-their-role),
each extended with Tiingo's own fields. The Connection tab is
`read_connection`, the Datasets tab `read_datasets`, each answering what its
page shows, as data, under the role's names.

A data plugin's pages show its connection and its datasets, never a price
(plans/the-lake-prices-the-book, ruled 2026-10-03), and never a secret: the
token is said to be set or not, and nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from meridian.roles import data


@dataclass(frozen=True)
class ConnectionRead(data.ConnectionRead):
    """Connection's common fields, then Tiingo's: the head's status and what
    it means, the source asked, the last check, the requests made in the
    last hour and day against the limits it keeps, the responses kept and
    where."""

    #: The head's status: `ok`, `busy`, `warn` or `error`, and what it means.
    state: str = ""
    said: str = ""
    source: str = ""
    checked_at: str = ""
    requests_last_hour: int = 0
    requests_last_day: int = 0
    responses_kept: int = 0
    kept_for: str = ""


@dataclass(frozen=True)
class Served(data.Served):
    """The one dataset as "Served" shows it, then Tiingo's: its history and
    venue (none: a fund strikes its NAV on no venue), and what it restated
    and kept unchanged since the plugin started."""

    history: str = ""
    venue: str = ""
    restated: int = 0
    unchanged: int = 0


@dataclass(frozen=True)
class Want(data.Want):
    """One want as "Wants" shows it, then Tiingo's: its ID, when, and whether
    it stands; declined, by reason."""

    want_id: str = ""
    at: str = ""
    standing: bool = False
    declined_as: str = ""


@dataclass(frozen=True)
class FundRead:
    """One listed fund: what Tiingo says it is, whether it is served, the
    deployment's record for it or why there is none, and the latest day
    recorded (a date, never its value)."""

    ticker: str
    name: str
    at_tiingo: str
    served: bool
    instrument_id: str
    from_setting: bool
    #: Not listed: read from its record when the lake wanted it.
    from_want: bool
    miss: str
    history_from: str
    latest_recorded: str


@dataclass(frozen=True)
class DatasetsRead(data.DatasetsRead):
    """Datasets' common fields, then Tiingo's: each fund listed or read for a
    want, and the days Tiingo gave that could not be read. Its rows are
    Tiingo's, each extending the role's."""

    served: list[Served] = field(default_factory=list)  # type: ignore[assignment]
    wants: list[Want] = field(default_factory=list)  # type: ignore[assignment]
    funds: list[FundRead] = field(default_factory=list)
    unconverted: list[str] = field(default_factory=list)
