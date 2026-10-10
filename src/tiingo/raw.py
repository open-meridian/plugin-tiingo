"""What Tiingo answered, kept as received, in the plugin's own storage.

A `dgm` keeps its source's raw records in the storage the deployment grants
an edge plugin (decisions/028, `meridian.edge.storage_dir()`), and every row
it records names the one it was converted from (`ObservationMeta.raw`). Here
that is each of Tiingo's responses: its address (which never holds the
token: it travels in a header, which is not kept), its status, when it was
received, and its body, one gzipped JSON file each, kept before anything is
read from it. The data is licensed for the account holder's own use, and it
stays in the deployment's storage.

One kind of raw record, `responses` (declaration.py), in units of a month
of receipt: `responses/<YYYY-MM>/`, each file `<received>-<call>.json.gz`,
its key that path. A month's unit is written to only in that month, so once
its last record is past the kind's window it is moved whole, as the SDK's
`responses_past_window` setting says: archived (`plugin.archive_unit`),
deleted (`plugin.delete_unit`, which a deployment's hold refuses, keeping
it) or kept. The window defaults to two years.

A NAV read again -- the latest days on every check, a day a want asks for
again -- names the response it was first read from with that value, not the
newest copy: the lake compares a row's raw record too, so a new reference
would restate every NAV unchanged. Which response first held each ticker's
day at each value is noted under `responses-first/<TICKER>.json` at the
storage's root, and rebuilt from the responses if lost (a NAV read again then
names the copy read that day, once).

Where no storage is granted -- a test, a preview -- the store keeps its
records in a directory of its own and moves nothing.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import meridian
from meridian import edge

from .vendor import Fetched

log = logging.getLogger("tiingo")

#: The kind of raw record, and its default window: two years.
RESPONSES = "responses"
DEFAULT_WINDOW_DAYS = 730
#: The longest a window may be set to, which the storage declaration states.
MOST_WINDOW_DAYS = 36500

_PAGE = re.compile(r"[^a-z0-9]+")
#: Which response first held each ticker's day at each value, at the
#: storage's root, a file per ticker.
FIRSTS = "responses-first"


def _ns(moment: datetime) -> int:
    return int(moment.timestamp() * 1_000_000) * 1000


def page_name(path: str) -> str:
    """A short name for the call a path is: `vigix-meta`, or `vigix-prices-`
    and its dates."""
    base, _, query = path.partition("?")
    parts = [p for p in base.split("/") if p and p not in ("tiingo", "daily")]
    if len(parts) == 1:
        parts.append("meta")
    asked = _query(query)
    dates = [asked[k] for k in ("startDate", "endDate") if k in asked]
    return _PAGE.sub("-", "-".join(parts + dates).lower()).strip("-") or "call"


def _query(text: str) -> dict[str, str]:
    from urllib.parse import parse_qsl

    return dict(parse_qsl(text))


@dataclass(frozen=True)
class Unit:
    """A month of responses: its path in storage, and what it holds."""

    unit: str
    records: int
    first_ns: int
    last_ns: int


class RawStore:
    """Responses kept under `root`: the granted storage, or a directory of
    the store's own where none is granted (`granted` False)."""

    def __init__(self, root: Path | None = None) -> None:
        granted = root if root is not None else edge.storage_dir()
        self.granted = granted is not None
        self.root = (
            Path(granted) if granted is not None else Path(tempfile.mkdtemp(prefix="tiingo-"))
        )

    def keep(self, fetched: Fetched) -> str:
        """Keep a response before anything is read from it; its key."""
        at = fetched.fetched_at.astimezone(UTC)
        unit = f"{RESPONSES}/{at:%Y-%m}"
        key = f"{unit}/{at:%Y%m%dT%H%M%S%fZ}-{page_name(fetched.path)}.json.gz"
        document = {
            "url": fetched.url,
            "status": fetched.status,
            "received_at": at.isoformat(),
            "body": fetched.text,
        }
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(".partial")
        partial.write_bytes(gzip.compress(json.dumps(document).encode(), mtime=0))
        partial.replace(target)
        return key

    def first(self, ticker: str, stated: str) -> str | None:
        """The key of the response a ticker's day was first read from at the
        value `stated` (`2026-10-08:245.55`); None if none is noted or
        storage no longer holds it."""
        key = self._firsts(ticker).get(stated)
        return key if key and (self.root / key).is_file() else None

    def note_first(self, ticker: str, stated: dict[str, str]) -> dict[str, str]:
        """Note each of `stated` -- a day at its value, to the key it was read
        from now -- unless one is noted and held already; the key each names."""
        firsts = self._firsts(ticker)
        out: dict[str, str] = {}
        changed = False
        for said, key in stated.items():
            held = firsts.get(said)
            if held and (self.root / held).is_file():
                out[said] = held
            else:
                firsts[said] = out[said] = key
                changed = True
        if changed:
            target = self.root / FIRSTS / f"{_PAGE.sub('-', ticker.upper())}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_suffix(".partial")
            partial.write_text(json.dumps(firsts, sort_keys=True, indent=0))
            partial.replace(target)
        return out

    def _firsts(self, ticker: str) -> dict[str, str]:
        target = self.root / FIRSTS / f"{_PAGE.sub('-', ticker.upper())}.json"
        try:
            held: dict[str, str] = json.loads(target.read_text())
        except (OSError, ValueError):
            return {}
        return held

    def read(self, key: str) -> dict[str, Any] | None:
        """A kept response by its key, or None where storage no longer holds it."""
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()) or not path.is_file():
            return None
        document: dict[str, Any] = json.loads(gzip.decompress(path.read_bytes()))
        return document

    def keys(self) -> list[str]:
        """Every kept response's key, oldest first."""
        held = self.root / RESPONSES
        if not held.is_dir():
            return []
        return sorted(str(p.relative_to(self.root)) for p in held.glob("*/*.json.gz"))

    def units(self) -> Iterator[Unit]:
        """Each month of responses in storage, oldest first."""
        held = self.root / RESPONSES
        if not held.is_dir():
            return
        for month in sorted(p for p in held.iterdir() if p.is_dir()):
            read = (_received(p.name) for p in month.glob("*.json.gz"))
            stamps = sorted(s for s in read if s is not None)
            if stamps:
                yield Unit(
                    str(month.relative_to(self.root)), len(stamps), _ns(stamps[0]), _ns(stamps[-1])
                )

    async def tend(
        self, plugin: meridian.Plugin, window_days: int, past_window: str, now: datetime
    ) -> dict[str, int]:
        """Move each month past the window as `past_window` says, and say on
        the heartbeat what storage holds; what it came to."""
        done = {"archived": 0, "deleted": 0, "kept": 0, "refused": 0}
        if not self.granted:
            return done
        cut = _ns(now - timedelta(days=window_days))
        this_month = f"{RESPONSES}/{now.astimezone(UTC):%Y-%m}"
        for unit in list(self.units()):
            if unit.last_ns >= cut or unit.unit == this_month:
                continue
            if past_window not in ("archived", "deleted"):
                done["kept"] += 1
                continue
            move = plugin.archive_unit if past_window == "archived" else plugin.delete_unit
            try:
                await move(
                    RESPONSES,
                    unit.unit,
                    record_count=unit.records,
                    first_received_ns=unit.first_ns,
                    last_received_ns=unit.last_ns,
                )
                done[past_window] += 1
            except meridian.MeridianError as refused:
                log.warning("%s: %s refused, kept: %s", unit.unit, past_window, refused)
                done["refused"] += 1
        plugin.stored = [self.span()]
        return done

    def span(self) -> Any:
        """What storage holds of the kind, for the heartbeat."""
        from meridian.v1 import sidecar_pb2

        units = list(self.units())
        return sidecar_pb2.StoredSpan(
            record_kind=RESPONSES,
            record_count=sum(u.records for u in units),
            first_received_ns=units[0].first_ns if units else 0,
            last_received_ns=units[-1].last_ns if units else 0,
        )


def _received(name: str) -> datetime | None:
    try:
        return datetime.strptime(name.split("-", 1)[0], "%Y%m%dT%H%M%S%fZ").replace(tzinfo=UTC)
    except ValueError:
        return None
