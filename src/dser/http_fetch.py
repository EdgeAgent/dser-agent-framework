"""Safe, bounded HTTP retrieval for source-attributed DSER observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
import ipaddress
import socket
from typing import Iterable
from urllib.parse import urljoin, urlsplit

import requests


DEFAULT_TIMEOUT_SECONDS = 8.0
MAX_RESPONSE_BYTES = 1_000_000
MAX_REDIRECTS = 3
ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/json")
USER_AGENT = "DSER-HTTP-Fetch/0.1 (+https://github.com/EdgeAgent/dser-agent-framework)"


class WebFetchError(ValueError):
    """Raised when a URL or HTTP response is not safe or suitable for DSER retrieval."""


@dataclass(frozen=True, slots=True)
class FetchedPage:
    """A bounded, source-attributed public HTTP response."""

    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    title: str | None
    text: str
    fetched_at: datetime
    bytes_read: int

    def excerpt(self, limit: int = 1_200) -> str:
        """Return a single-line text excerpt suitable for claim support metadata."""

        compact = " ".join(self.text.split())
        return compact[:limit]


class _TextExtractor(HTMLParser):
    """Small dependency-free HTML-to-text extractor for demo retrieval."""

    ignored_tags = {"script", "style", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._title: list[str] = []
        self._ignored_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: Iterable[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in self.ignored_tags:
            self._ignored_depth += 1
        if lowered == "title" and self._ignored_depth == 0:
            self._in_title = True
        if lowered in {"p", "div", "li", "br", "h1", "h2", "h3", "article", "section"} and self._ignored_depth == 0:
            self._chunks.append(" ")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._in_title = False
        if lowered in self.ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1
        if lowered in {"p", "div", "li", "br", "h1", "h2", "h3", "article", "section"} and self._ignored_depth == 0:
            self._chunks.append(" ")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        self._chunks.append(data)
        if self._in_title:
            self._title.append(data)

    @property
    def text(self) -> str:
        return " ".join("".join(self._chunks).split())

    @property
    def title(self) -> str | None:
        value = " ".join("".join(self._title).split())
        return value or None


def _validate_public_url(url: str) -> tuple[str, int]:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise WebFetchError("Only http and https URLs are permitted")
    if not parsed.hostname:
        raise WebFetchError("A URL must include a hostname")
    if parsed.username or parsed.password:
        raise WebFetchError("URLs with embedded credentials are not permitted")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise WebFetchError("URL has an invalid port") from exc
    if port not in {80, 443}:
        raise WebFetchError("Only standard public HTTP(S) ports 80 and 443 are permitted")
    return parsed.hostname, port


def _assert_public_destination(url: str) -> None:
    hostname, port = _validate_public_url(url)
    try:
        records = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise WebFetchError(f"Could not resolve hostname: {hostname}") from exc
    if not records:
        raise WebFetchError(f"Could not resolve hostname: {hostname}")
    for record in records:
        address = record[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise WebFetchError("Hostname resolved to an invalid address") from exc
        if not ip.is_global:
            raise WebFetchError("Private, loopback, link-local, multicast, and reserved destinations are blocked")


def _read_limited(response: requests.Response, max_bytes: int) -> bytes:
    declared_length = response.headers.get("Content-Length")
    if declared_length:
        try:
            if int(declared_length) > max_bytes:
                raise WebFetchError(f"Response exceeds the {max_bytes} byte limit")
        except ValueError:
            pass
    content = bytearray()
    for chunk in response.iter_content(chunk_size=16_384):
        content.extend(chunk)
        if len(content) > max_bytes:
            raise WebFetchError(f"Response exceeds the {max_bytes} byte limit")
    return bytes(content)


def _extract_text(content: bytes, content_type: str, encoding: str | None) -> tuple[str | None, str]:
    decoded = content.decode(encoding or "utf-8", errors="replace")
    if content_type.startswith("text/html"):
        parser = _TextExtractor()
        parser.feed(decoded)
        parser.close()
        return parser.title, parser.text
    return None, " ".join(decoded.split())


def fetch_public_page(
    url: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = MAX_RESPONSE_BYTES,
    session: requests.Session | None = None,
) -> FetchedPage:
    """Fetch a public text page with bounds, redirect validation, and attribution.

    This helper is designed for public, unauthenticated content only. It blocks
    private/loopback destinations, credential-bearing URLs, non-standard ports,
    unsupported content types, oversized responses, and redirect targets that
    do not pass the same public-destination validation.
    """

    if not 0 < timeout_seconds <= 30:
        raise WebFetchError("timeout_seconds must be greater than 0 and no more than 30")
    if not 1_024 <= max_bytes <= MAX_RESPONSE_BYTES:
        raise WebFetchError(f"max_bytes must be between 1024 and {MAX_RESPONSE_BYTES}")

    requested_url = url.strip()
    current_url = requested_url
    active_session = session or requests.Session()
    active_session.trust_env = False
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,text/plain,application/json;q=0.9,*/*;q=0.1"}

    for redirect_count in range(MAX_REDIRECTS + 1):
        _assert_public_destination(current_url)
        try:
            response = active_session.get(
                current_url,
                headers=headers,
                timeout=timeout_seconds,
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            raise WebFetchError(f"HTTP request failed: {exc}") from exc

        try:
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("Location")
                if not location:
                    raise WebFetchError("Redirect response omitted a Location header")
                if redirect_count >= MAX_REDIRECTS:
                    raise WebFetchError(f"Redirect limit exceeded ({MAX_REDIRECTS})")
                current_url = urljoin(current_url, location)
                continue

            if not 200 <= response.status_code < 300:
                raise WebFetchError(f"HTTP response status {response.status_code}")
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                raise WebFetchError("Only text/html, text/plain, and application/json responses are supported")
            content = _read_limited(response, max_bytes)
            title, text = _extract_text(content, content_type, response.encoding)
            if not text:
                raise WebFetchError("The response did not contain extractable text")
            return FetchedPage(
                requested_url=requested_url,
                final_url=current_url,
                status_code=response.status_code,
                content_type=content_type,
                title=title,
                text=text,
                fetched_at=datetime.now(UTC),
                bytes_read=len(content),
            )
        finally:
            response.close()

    raise WebFetchError("Redirect handling failed")
