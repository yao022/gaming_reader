"""Tests for the AI text filter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from game_text_reader.config import Config
from game_text_reader.filter import TextFilter


def test_filter_disabled_returns_raw_text():
    config = Config(ai_filter_enabled=False)
    f = TextFilter(config)
    assert f.filter("some raw text") == "some raw text"


def test_filter_empty_text():
    config = Config(ai_filter_enabled=False)
    f = TextFilter(config)
    assert f.filter("") == ""
    assert f.filter("   ") == ""


def test_filter_no_api_key_disables():
    with patch.dict("os.environ", {}, clear=True):
        config = Config(ai_filter_enabled=True)
        f = TextFilter(config)
        assert not f._enabled
        assert f.filter("raw text") == "raw text"


def test_filter_calls_api():
    config = Config(ai_filter_enabled=False)
    f = TextFilter(config)
    f._enabled = True

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Filtered narrative text")]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    f._client = mock_client

    result = f.filter("HP: 100 | Ammo: 12\nYou found a mysterious letter on the desk.")
    assert result == "Filtered narrative text"


def test_filter_no_text_marker():
    config = Config(ai_filter_enabled=False)
    f = TextFilter(config)
    f._enabled = True

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="[NO TEXT]")]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    f._client = mock_client

    result = f.filter("HP: 100 | Settings | Options")
    assert result == ""
