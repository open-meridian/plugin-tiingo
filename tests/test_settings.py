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


def test_the_funds_are_read_from_a_typed_delivery() -> None:
    """open-meridian 0.35.2 delivers the settings typed (`meridian.run`'s
    `on_settings`): a table's rows a tuple, the SDK's own settings beside."""
    from tiingo.settings import DECLARED

    delivered = DECLARED._of(  # type: ignore[attr-defined]
        {
            "funds": [{"ticker": "vigix", "instrument": "LCL-1"}],
            "responses_window_days": 30,
            "responses_past_window": "kept",
        },
        (TOKEN,),
        (),
    )
    config = config_from(delivered.values, delivered.missing)
    assert [(f.ticker, f.instrument_id) for f in config.funds] == [("VIGIX", "LCL-1")]
    assert config.window_days == 30 and config.missing == (TOKEN,)
