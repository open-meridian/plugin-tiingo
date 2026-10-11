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

from conftest import CUSTODIAN, CUSTODIANS, feed, held, want


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
    # The data role's sections, in its order, then Tiingo's Funds.
    assert text.index("<h2>Served</h2>") < text.index("<h2>Wants</h2>")
    assert text.index("<h2>Subjects</h2>") < text.index("<h2>Funds</h2>")
    assert "tiingo:daily" in text and "kept; personal use" in text
    assert "Not licensed yet" in text
    assert 'data-ticker="VIGIX" data-served="yes"' in text
    assert 'data-ticker="VOO" data-served="no"' in text and "not a mutual fund (NYSE)" in text
    assert 'data-ticker="NOSUCH" data-served="no"' in text and "not found" in text
    assert "Kept current" in text and "2026-09-22" in text


def test_datasets_lists_a_fund_read_from_the_record_a_want_named(tmp_path: Path) -> None:
    work = feed(tmp_path)
    held(work.plugin, {CUSTODIAN: CUSTODIANS})

    async def run() -> None:
        await work.check()
        await work.on_want(want("w-vtsax", [CUSTODIAN], day="2026-10-08"))

    asyncio.run(run())
    hold(work)
    client = PageClient(pages)
    text = client.get(DATASETS, "admin").text
    assert 'data-ticker="VTSAX" data-served="yes"' in text and CUSTODIAN in text
    assert "read from the record when the lake wanted it" in text
    funds = client.call_tool("read_datasets").data["funds"]
    vtsax = next(f for f in funds if f["ticker"] == "VTSAX")
    assert vtsax["from_want"] and not vtsax["from_setting"] and vtsax["instrument_id"] == CUSTODIAN
    client.assert_no_account_data("147.4")


def test_the_tools_answer_what_the_pages_show(client: PageClient) -> None:
    assert {t.name for t in pages.tools} == {"read_connection", "read_datasets"}
    connection = client.call_tool("read_connection")
    assert connection.outcome == "unchanged"
    assert connection.data["mode"] == "Sample data"
    assert connection.data["credentials"] == [{"label": "API token", "set": False}]
    assert connection.data["sessions"] is None and connection.data["requests_last_hour"] >= 0
    datasets = client.call_tool("read_datasets").data
    (served,) = datasets["served"]
    assert served["arrives"] == "push, pull" and served["recorded"] >= 1
    assert served["licensed"] is False and served["last_recorded"]
    assert [w["state"] for w in datasets["wants"]] == [
        "Kept current",
        "Answered, standing",
        "Answered",
    ]
    vigix = next(f for f in datasets["funds"] if f["ticker"] == "VIGIX")
    assert vigix["served"] and vigix["latest_recorded"] == "2026-10-09"
    assert vigix["history_from"] == "1998-05-14"
    assert vigix["instrument_id"] in client.get(DATASETS, "admin").text


def test_waiting_for_the_token(tmp_path: Path) -> None:
    work = feed(tmp_path)
    work.configure(Config(funds=(Fund("VIGIX"),), missing=("tiingo_api_token",)))
    hold(work)
    client = PageClient(pages)
    text = client.get(CONNECTION, "admin").text
    # The role's "not set up yet" state, linking to core's Settings tab.
    assert "No key yet" in text and 'data-om-opens="settings"' in text
    assert "API token: not set" in text and "Does not stream" in text
    assert client.call_tool("read_connection").data["mode"] == "No key"


def test_the_token_is_never_shown(tmp_path: Path) -> None:
    work = feed(tmp_path)
    work.configure(Config(token="abc123secret", funds=(Fund("VIGIX"),)))
    hold(work)
    client = PageClient(pages)
    for path in (CONNECTION, DATASETS):
        assert "abc123secret" not in client.get(path, "admin").text
    assert "abc123secret" not in str(client.call_tool("read_connection").json)
    assert "API token: set" in client.get(CONNECTION, "admin").text


def test_before_anything(tmp_path: Path) -> None:
    page_module._held.clear()
    assert "No key yet" in PageClient(pages).get(CONNECTION, "admin").text
    text = PageClient(pages).get(DATASETS, "admin").text
    assert "No fund listed" in text and "No wants yet" in text


def test_a_licensed_dataset_is_said_so(client: PageClient) -> None:
    page_module._held["feed"].status.licensed = frozenset({"tiingo:daily"})
    (served,) = client.call_tool("read_datasets").data["served"]
    assert served["licensed"] is True


def test_the_figures_are_the_data_roles_in_its_order(client: PageClient) -> None:
    from tiingo.page import figures

    work = page_module._held["feed"]
    said = figures(work.status, work)
    assert [f.label for f in said] == [
        "Connection",
        "Entitled at the vendor",
        "Stream",
        "Last recorded",
        "Rate use",
    ]
    assert said[0].value == "Sample data" and said[2].value == "Does not stream"


def test_the_funds_are_searched(client: PageClient) -> None:
    text = client.get(DATASETS, "admin", q="vanguard growth").text
    assert 'type="search"' in text and 'data-ticker="VIGIX"' in text
    assert 'data-ticker="VOO"' not in text and "1 of 3" in text
    assert "No fund matches" in client.get(DATASETS, "admin", q="bond").text
    assert len(client.call_tool("read_datasets").data["funds"]) == 3
