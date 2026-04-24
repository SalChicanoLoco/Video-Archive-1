from app.providers.plugins import ProviderPluginError, parse_plugin_specs


def test_parse_plugin_specs_empty() -> None:
    assert parse_plugin_specs("") == []


def test_parse_plugin_specs_valid() -> None:
    parsed = parse_plugin_specs("whisper=plugins.whisper:WhisperProvider")
    assert parsed == [("whisper", "plugins.whisper", "WhisperProvider")]


def test_parse_plugin_specs_invalid() -> None:
    try:
        parse_plugin_specs("bad-format")
    except ProviderPluginError:
        assert True
    else:
        assert False
