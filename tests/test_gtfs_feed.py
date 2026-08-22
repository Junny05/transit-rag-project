import requests
import pytest
from google.transit import gtfs_realtime_pb2

from app.gtfs_feed import parse_alert_strings, fetch_raw_feed, FeedFetchError


def _build_feed_bytes(alerts_data):
    """alerts_data: list of dicts like {"en": "text"} or {} for entities
    with no english translation, or None for a non-alert entity."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    for i, translations in enumerate(alerts_data):
        entity = feed.entity.add()
        entity.id = str(i)
        if translations is None:
            # Entity with no alert field at all (e.g. a pure vehicle-position entity)
            continue
        for lang, text in translations.items():
            t = entity.alert.header_text.translation.add()
            t.language = lang
            t.text = text
    return feed.SerializeToString()


def test_parse_extracts_english_alerts():
    raw = _build_feed_bytes([{"en": "L train delayed"}, {"en": "4/5/6 running with delays"}])
    result = parse_alert_strings(raw)
    assert result == ["L train delayed", "4/5/6 running with delays"]


def test_parse_skips_non_english_translations():
    raw = _build_feed_bytes([{"es": "Retraso del tren L"}])
    result = parse_alert_strings(raw)
    assert result == []


def test_parse_skips_entities_with_no_alert_field():
    raw = _build_feed_bytes([None, {"en": "Signal problems on the A line"}])
    result = parse_alert_strings(raw)
    assert result == ["Signal problems on the A line"]


def test_parse_handles_empty_feed():
    raw = _build_feed_bytes([])
    assert parse_alert_strings(raw) == []


def test_parse_skips_empty_text_translation():
    raw = _build_feed_bytes([{"en": ""}, {"en": "Real alert"}])
    result = parse_alert_strings(raw)
    assert result == ["Real alert"]


def test_parse_raises_on_garbage_bytes():
    with pytest.raises(FeedFetchError):
        parse_alert_strings(b"this is not a valid protobuf message \xff\xfe")


def test_fetch_raw_feed_retries_on_network_error(monkeypatch):
    call_count = {"n": 0}

    def flaky_get(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise requests.ConnectionError("simulated network blip")
        response = requests.Response()
        response.status_code = 200
        response._content = b"ok"
        return response

    monkeypatch.setattr(requests, "get", flaky_get)
    result = fetch_raw_feed("https://fake-url", "fake-key")
    assert result == b"ok"
    assert call_count["n"] == 3


def test_fetch_raw_feed_raises_after_exhausting_retries(monkeypatch):
    def always_fails(*args, **kwargs):
        raise requests.ConnectionError("persistent outage")

    monkeypatch.setattr(requests, "get", always_fails)
    with pytest.raises(requests.ConnectionError):
        fetch_raw_feed("https://fake-url", "fake-key")
