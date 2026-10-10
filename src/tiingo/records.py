"""The typed records the pages answer, for a person's page and an agent's
tool alike (contract v12; spec/a-deployment-serves-its-mcp): the Connection
tab is `read_connection`, the Datasets tab `read_datasets`, each answering
what its page shows, as data.

A `dgm`'s pages show its connection and its datasets, never a price
(plans/the-lake-prices-the-book, ruled 2026-10-03), and never a secret: the
token is said to be set or not, and nothing more.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConnectionRead:
    """How the plugin reaches Tiingo, and how it last went."""

    #: `live`, `synthetic`, or `waiting` (no token, and not synthetic).
    mode: str
    #: The head's status: `ok`, `busy`, `warn` or `error`, and what it means.
    state: str
    said: str
    #: Whether the API token is set: never its value.
    token_set: bool
    #: The settings the plugin waits for, by their labels.
    waiting_for: list[str]
    source: str
    checked_at: str
    error: str
    #: Requests made in the last hour and day, against the limits it keeps.
    requests_last_hour: int
    requests_last_day: int
    limits: str
    pages_read: int
    responses_kept: int
    kept_for: str


@dataclass(frozen=True)
class DatasetRead:
    dataset: str
    vendor: str
    data_types: list[str]
    modes: list[str]
    cadence: str
    day: str
    history: str
    venue: str
    licence: str


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
class WantRead:
    want_id: str
    asked: str
    subjects: int
    recorded: int
    declined: str
    at: str
    standing: bool


@dataclass(frozen=True)
class DatasetsRead:
    """What the plugin serves: its dataset, the funds listed, the standing
    wants it keeps current and the wants it answered lately."""

    dataset: DatasetRead
    #: What the token entitles the plugin to at Tiingo, as far as it can say.
    entitled_at_vendor: str
    funds: list[FundRead] = field(default_factory=list)
    unconverted: list[str] = field(default_factory=list)
    standing: list[WantRead] = field(default_factory=list)
    wants: list[WantRead] = field(default_factory=list)
