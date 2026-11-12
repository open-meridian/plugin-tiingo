"""The catalogue, from code, as the deployment approves it."""

from __future__ import annotations

from tiingo.declaration import DECLARATION
from tiingo.declared import DAILY_DATASET, mode_name


def test_one_daily_dataset_of_navs() -> None:
    assert [d.key for d in DECLARATION.catalogue] == ["daily"]
    assert list(DAILY_DATASET.data_types) == ["meridian.v1.Price"]
    assert [mode_name(m) for m in DAILY_DATASET.modes] == ["push", "pull"]
    assert DAILY_DATASET.day_time_zone == "America/New_York"
    assert DAILY_DATASET.day_end_minute == 960
    assert DAILY_DATASET.cadence == 86_400 and DAILY_DATASET.history == 0
    assert not DAILY_DATASET.venue_id


def test_the_navs_delay_is_eight_hours_from_the_days_end_to_midnight() -> None:
    # Contract v27: a fund strikes its NAV at 16:00 New York; Tiingo has it
    # after midnight.
    assert DAILY_DATASET.declared_delay_ns == 8 * 3_600 * 10**9
    assert DAILY_DATASET._to_json()["declared_delay_ns"] == 8 * 3_600 * 10**9


def test_tiingos_terms_are_described_in_words() -> None:
    # Contract 30 (ruling 1032): Tiingo's terms in words, never a licence.
    terms = DAILY_DATASET.terms_and_pricing
    assert "internal and personal use" in terms and "no redistribution" in terms
    assert len(terms) <= 2000


def test_a_gap_is_asked_for_again() -> None:
    # Contract 30: Tiingo serves each fund's history, so a gap is backfilled;
    # a NAV is struck once a day, in no trading session.
    assert DAILY_DATASET.gap_recovery == "backfill"
    assert not DAILY_DATASET.sessions_calendar_id


def test_the_token_is_declared_secret() -> None:
    assert any(s.name == "tiingo_api_token" and s.secret for s in DECLARATION.settings)
