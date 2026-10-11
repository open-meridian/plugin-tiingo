"""The settings: the token secret, the funds a table."""

from __future__ import annotations

from tiingo.settings import SETTINGS, TOKEN, config_from


def test_the_token_is_a_secret_setting() -> None:
    [token] = [s for s in SETTINGS if s.name == TOKEN]
    assert token.secret and token.required


def test_the_funds_table_read() -> None:
    config = config_from(
        {
            "funds": [
                {"ticker": " vigix "},
                {"ticker": "VIGIX"},
                {"ticker": "VTSAX", "instrument": "LCL-9"},
            ],
            "tiingo_api_token": "abc",
        }
    )
    assert [(f.ticker, f.instrument_id) for f in config.funds] == [
        ("VIGIX", ""),
        ("VTSAX", "LCL-9"),
    ]
    assert config.token == "abc" and not config.waiting
    assert "abc" not in repr(config)
    assert config_from({}).waiting
    assert not config_from({"sample_data": True}).waiting
