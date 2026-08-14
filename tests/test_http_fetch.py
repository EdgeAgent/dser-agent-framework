from __future__ import annotations

from datetime import UTC, datetime
import socket
from unittest.mock import patch
import unittest

from dser.http_fetch import FetchedPage, WebFetchError, fetch_public_page
from dser.local import demo_payloads, run_local_decision


PUBLIC_ADDRINFO = [
    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
]
PRIVATE_ADDRINFO = [
    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
]


class FakeResponse:
    def __init__(self, status_code: int, headers: dict[str, str], content: bytes, encoding: str = "utf-8") -> None:
        self.status_code = status_code
        self.headers = headers
        self._content = content
        self.encoding = encoding
        self.closed = False

    @property
    def is_redirect(self) -> bool:
        return 300 <= self.status_code < 400

    @property
    def is_permanent_redirect(self) -> bool:
        return self.status_code in {301, 308}

    def iter_content(self, chunk_size: int):
        for index in range(0, len(self._content), chunk_size):
            yield self._content[index : index + chunk_size]

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.urls: list[str] = []
        self.trust_env = True

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.urls.append(url)
        return self.responses.pop(0)


class HttpFetchTests(unittest.TestCase):
    @patch("dser.http_fetch.socket.getaddrinfo", return_value=PUBLIC_ADDRINFO)
    def test_fetch_extracts_html_title_and_visible_text(self, _mock_dns: object) -> None:
        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {"Content-Type": "text/html; charset=utf-8"},
                    b"<html><head><title>DSER docs</title><style>hidden</style></head><body><h1>Hello</h1><p>Visible text.</p><script>ignored()</script></body></html>",
                )
            ]
        )

        page = fetch_public_page("https://example.com/docs", session=session)

        self.assertEqual(page.title, "DSER docs")
        self.assertEqual(page.text, "DSER docs Hello Visible text.")
        self.assertEqual(page.content_type, "text/html")
        self.assertFalse(session.trust_env)

    @patch("dser.http_fetch.socket.getaddrinfo", return_value=PUBLIC_ADDRINFO)
    def test_redirect_target_is_fetched_after_validation(self, _mock_dns: object) -> None:
        session = FakeSession(
            [
                FakeResponse(302, {"Location": "/final"}, b""),
                FakeResponse(200, {"Content-Type": "text/plain"}, b"Final public content"),
            ]
        )

        page = fetch_public_page("https://example.com/start", session=session)

        self.assertEqual(page.final_url, "https://example.com/final")
        self.assertEqual(session.urls, ["https://example.com/start", "https://example.com/final"])
        self.assertEqual(page.text, "Final public content")

    @patch("dser.http_fetch.socket.getaddrinfo", return_value=PRIVATE_ADDRINFO)
    def test_private_destination_is_blocked_before_http_request(self, _mock_dns: object) -> None:
        session = FakeSession([])

        with self.assertRaisesRegex(WebFetchError, "Private"):
            fetch_public_page("http://localhost", session=session)

        self.assertEqual(session.urls, [])

    def test_credential_and_nonstandard_port_urls_are_blocked(self) -> None:
        with self.assertRaisesRegex(WebFetchError, "credentials"):
            fetch_public_page("https://user:secret@example.com")
        with self.assertRaisesRegex(WebFetchError, "ports"):
            fetch_public_page("https://example.com:8080")

    @patch("dser.local.fetch_public_page")
    def test_local_runner_converts_fetched_page_to_document_evidence(self, mock_fetch: object) -> None:
        page = FetchedPage(
            requested_url="https://example.com",
            final_url="https://example.com/article",
            status_code=200,
            content_type="text/html",
            title="Example article",
            text="A source-attributed public page.",
            fetched_at=datetime.now(UTC),
            bytes_read=34,
        )
        mock_fetch.return_value = page  # type: ignore[attr-defined]
        payload = demo_payloads()["clean"]
        payload["fetch_url"] = "https://example.com"

        result = run_local_decision(payload)

        self.assertEqual(result["claims"][0]["source"], "document")
        self.assertEqual(result["claims"][0]["provenance"], "https://example.com/article")
        self.assertEqual(result["web_fetch"]["title"], "Example article")


if __name__ == "__main__":
    unittest.main()
