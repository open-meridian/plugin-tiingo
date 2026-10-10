"""Tiingo's responses kept as received, never the token, and moved past
their window."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from tiingo.raw import RawStore, page_name
from tiingo.vendor import Fetched

from conftest import AT


def fetched(at: datetime, path: str = "/tiingo/daily/vigix") -> Fetched:
    return Fetched(path, 200, b'{"ticker":"vigix"}', at)


def test_a_response_kept_and_read_back(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    key = store.keep(fetched(AT))
    assert key == "responses/2026-10/20261010T110000000000Z-vigix-meta.json.gz"
    kept = store.read(key)
    assert kept is not None and kept["body"] == '{"ticker":"vigix"}' and kept["status"] == 200
    assert kept["url"] == "https://api.tiingo.com/tiingo/daily/vigix"
    assert set(kept) == {"url", "status", "received_at", "body"}
    assert store.read("../outside.json.gz") is None
    path = "/tiingo/daily/vigix/prices?startDate=2026-09-30&endDate=2026-10-10"
    assert page_name(path) == "vigix-prices-2026-09-30-2026-10-10"


class Mover:
    def __init__(self) -> None:
        self.moved: list[tuple[str, str, int]] = []
        self.stored: list[Any] = []

    async def archive_unit(self, kind: str, unit: str, **span: int) -> None:
        self.moved.append(("archived", unit, span["record_count"]))

    async def delete_unit(self, kind: str, unit: str, **span: int) -> None:
        self.moved.append(("deleted", unit, span["record_count"]))


async def test_months_past_the_window_moved_as_the_setting_says(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    store.keep(fetched(AT - timedelta(days=400)))
    store.keep(fetched(AT - timedelta(days=399)))
    store.keep(fetched(AT))
    mover = Mover()
    done = await store.tend(mover, 365, "archived", AT)  # type: ignore[arg-type]
    assert done["archived"] == 1
    assert mover.moved == [("archived", "responses/2025-09", 2)]
    kept = await store.tend(mover, 365, "kept", AT)  # type: ignore[arg-type]
    assert kept["kept"] == 1
    assert mover.stored[0].record_count == 3


async def test_nothing_moved_without_granted_storage() -> None:
    store = RawStore(None)
    store.granted = False
    store.keep(fetched(datetime(2020, 1, 1, tzinfo=UTC)))
    mover = Mover()
    assert (await store.tend(mover, 1, "deleted", AT))["deleted"] == 0  # type: ignore[arg-type]
    assert mover.moved == []
