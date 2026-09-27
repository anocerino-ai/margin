"""Bounded RSS fetch: public address validation, pinned DNS and redirect revalidation."""

import http.client
import ipaddress
import socket
import ssl
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import feedparser


class FetchError(ValueError):
    pass


def normalize_url(url: str) -> str:
    p = urlsplit(url.strip())
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        raise FetchError("INVALID_PUBLIC_URL")
    if p.port not in (None, 80, 443):
        raise FetchError("UNSUPPORTED_PORT")
    host = p.hostname.lower().encode("idna").decode()
    netloc = f"[{host}]" if ":" in host else host
    if p.port and not (p.scheme == "https" and p.port == 443 or p.scheme == "http" and p.port == 80):
        netloc += f":{p.port}"
    query = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}
    ]
    return urlunsplit((p.scheme, netloc, p.path or "/", urlencode(query), ""))


def public_addresses(url):
    p = urlsplit(normalize_url(url))
    try:
        addresses = list(
            dict.fromkeys(
                x[4][0]
                for x in socket.getaddrinfo(
                    p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM
                )
            )
        )
    except OSError as exc:
        raise FetchError("DNS_FAILED") from exc
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise FetchError("NON_PUBLIC_ADDRESS")
    return addresses


def fetch_public(url: str, limit=2_000_000) -> bytes:
    for _ in range(5):
        url = normalize_url(url)
        p = urlsplit(url)
        addresses = public_addresses(url)
        port = p.port or (443 if p.scheme == "https" else 80)
        connection = (
            http.client.HTTPSConnection(p.hostname, port, timeout=15, context=ssl.create_default_context())
            if p.scheme == "https"
            else http.client.HTTPConnection(p.hostname, port, timeout=15)
        )
        # Pin the validated address; TLS SNI and certificate validation still use the original hostname.
        connection._create_connection = (
            lambda address, timeout, source_address=None, ip=addresses[0], dest_port=port: (
                socket.create_connection((ip, dest_port), timeout, source_address)
            )
        )
        try:
            connection.request(
                "GET",
                urlunsplit(("", "", p.path or "/", p.query, "")),
                headers={
                    "User-Agent": "Margin/0.2 RSS reader",
                    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise FetchError("INVALID_REDIRECT")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise FetchError(f"RSS_HTTP_{response.status}")
            body = response.read(limit + 1)
            if len(body) > limit:
                raise FetchError("RSS_TOO_LARGE")
            return body
        except (OSError, http.client.HTTPException) as exc:
            raise FetchError("RSS_FETCH_FAILED") from exc
        finally:
            connection.close()
    raise FetchError("TOO_MANY_REDIRECTS")


class RSSProvider:
    def __init__(self, fetch=fetch_public):
        self.fetch = fetch

    def entries(self, url, limit=50):
        body = self.fetch(url)
        if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
            raise FetchError("UNSAFE_XML")
        parsed = feedparser.parse(body)
        if not parsed.version:
            raise FetchError("INVALID_FEED")
        result = []
        for entry in parsed.entries[:limit]:
            title = entry.get("title", "").strip()
            if not title or not entry.get("link"):
                continue
            try:
                link = normalize_url(entry.link)
            except ValueError:
                continue
            date = entry.get("published_parsed") or entry.get("updated_parsed")
            published = datetime(*date[:6], tzinfo=UTC).isoformat() if date else None
            result.append(
                {"title": title[:2000], "url": link, "rss_guid": entry.get("id"), "published_at": published}
            )
        return result
