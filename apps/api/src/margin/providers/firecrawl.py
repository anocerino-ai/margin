import httpx

from margin.providers.rss import normalize_url, public_addresses


class FirecrawlProvider:
    def __init__(self, token, client=None):
        self.token = token
        self.client = client or httpx.Client(timeout=75)

    def crawl(self, url, force_refresh=False):
        url = normalize_url(url)
        public_addresses(url)
        response = self.client.post(
            "https://api.firecrawl.dev/v2/scrape",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True,
                "timeout": 60000,
                "maxAge": 0 if force_refresh else 172800000,
            },
        )
        response.raise_for_status()
        data = response.json()
        markdown = data.get("data", {}).get("markdown", "")
        if not data.get("success") or not markdown.strip():
            raise ValueError("EMPTY_CRAWL")
        if len(markdown) > 1_000_000:
            raise ValueError("CRAWL_TOO_LARGE")
        return markdown
