import logging
from typing import List

import requests
from google.transit import gtfs_realtime_pb2
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

logger = logging.getLogger(__name__)


class FeedFetchError(Exception):
    """Raised when the GTFS-RT feed can't be fetched or parsed."""


@retry(
    stop=stop_after_attempt(settings.MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((requests.RequestException,)),
    reraise=True,
)
def fetch_raw_feed(url: str, api_key: str) -> bytes:
    """Fetch the raw GTFS-RT protobuf bytes. Retries on network errors."""
    response = requests.get(
        url,
        headers={"x-api-key": api_key},
        timeout=settings.HTTP_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.content


def parse_alert_strings(raw_bytes: bytes) -> List[str]:
    """Parse GTFS-RT protobuf bytes into a list of English alert header texts.

    Skips entities that don't have an alert, or that don't have an English
    translation, instead of throwing — a single malformed entity shouldn't
    take down the whole feed.
    """
    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(raw_bytes)
    except Exception as exc:
        raise FeedFetchError(f"Failed to parse GTFS-RT feed: {exc}") from exc

    alert_strings: List[str] = []
    for entity in feed.entity:
        if not entity.HasField("alert"):
            continue
        for translation in entity.alert.header_text.translation:
            if translation.language == "en" and translation.text:
                alert_strings.append(translation.text)

    return alert_strings


def get_current_alerts(url: str = None, api_key: str = None) -> List[str]:
    """Fetch + parse in one call. Raises FeedFetchError on failure."""
    url = url or settings.MTA_FEED_URL
    api_key = api_key or settings.MTA_API_KEY
    try:
        raw = fetch_raw_feed(url, api_key)
    except requests.RequestException as exc:
        raise FeedFetchError(f"Failed to fetch GTFS-RT feed after retries: {exc}") from exc
    return parse_alert_strings(raw)
