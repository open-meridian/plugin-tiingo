"""The two pages under Manage, and their read tools: what each shows, to
whom, never a NAV or the token, and that a tool answers what its page shows."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from meridian.testing import PageClient

from tiingo import page as page_module
from tiingo.page import CONNECTION, DATASETS, hold, pages
from tiingo.settings import Config, Fund

from conftest import feed, want


@pytest.fixture
def client(tmp_path: Path) -> PageClient:
    work = feed(tmp_path)

    async def run() -> None:
        await work.check()
        vigix = work.status.funds["VIGIX"].instrument_id
        await work.on_want(want("w-0922", [vigix], day="2026-09-22"))
        await work.on_want(want("w-standing", [vigix], standing=True))

    asyncio.run(run())
    hold(work)
    return PageClient(pages)


def test_each_page_is_managed_alone(client: PageClient) -> None:
    served = {(r.page.path, r.level): r.response.status for r in client.every_page()}
    assert served == {
        (CONNECTION, "admin"): 200,
        (CONNECTION, "write"): 403,
        (CONNECTION, "read"): 403,
        (DATASETS, "admin"): 200,
        (DATASETS, "write"): 403,
        (DATASETS, "read"): 403,
    }
    # No NAV on any page: a fund's prices are the reading roles' to show.
    client.assert_no_account_data("245.55", "244.82", "243.9")


def test_datasets_lists_each_fund_and_what_tiingo_says_it_is(client: PageClient) -> None:
    text = client.get(DATASETS, "admin").text
    assert "tiingo:daily" in text and "One person" in text
    assert 'data-ticker="VIGIX" data-served="yes"' in text
    assert 'data-ticker="VOO" data-served="no"' in text and "not a mutual fund (NYSE)" in text
    assert 'data-ticker="NOSUCH" data-served="no"' in text and "not found" in text
    assert "1 standing" in text and "2026-09-22: 1 recorded" in text


def test_the_tools_answer_what_the_pages_show(client: PageClient) -> None:
    assert {t.name for t in pages.tools} == {"read_connection", "read_datasets"}
    connection = client.call_tool("read_connection")
    assert connection.outcome == "unchanged"
    assert connection.data["mode"] == "synthetic" and connection.data["token_set"] is False
    assert connection.data["requests_last_hour"] >= 0
    datasets = client.call_tool("read_datasets").data
    assert datasets["dataset"]["modes"] == ["push", "pull"]
    vigix = next(f for f in datasets["funds"] if f["ticker"] == "VIGIX")
    assert vigix["served"] and vigix["latest_recorded"] == "2026-10-09"
    assert vigix["history_from"] == "1998-05-14"
    assert vigix["instrument_id"] in client.get(DATASETS, "admin").text


def test_waiting_for_the_token(tmp_path: Path) -> None:
    work = feed(tmp_path)
    work.configure(Config(funds=(Fund("VIGIX"),), missing=("tiingo_api_token",)))
    hold(work)
    text = PageClient(pages).get(CONNECTION, "admin").text
    assert "Waiting for the API token" in text and "Not set" in text


def test_the_token_is_never_shown(tmp_path: Path) -> None:
    work = feed(tmp_path)
    work.configure(Config(token="abc123secret", funds=(Fund("VIGIX"),)))
    hold(work)
    client = PageClient(pages)
    for path in (CONNECTION, DATASETS):
        assert "abc123secret" not in client.get(path, "admin").text
    assert "abc123secret" not in str(client.call_tool("read_connection").json)
    assert "Set" in client.get(CONNECTION, "admin").text


def test_before_anything(tmp_path: Path) -> None:
    page_module._held.clear()
    assert "Waiting for the API token" in PageClient(pages).get(CONNECTION, "admin").text
    assert "No fund listed" in PageClient(pages).get(DATASETS, "admin").text
