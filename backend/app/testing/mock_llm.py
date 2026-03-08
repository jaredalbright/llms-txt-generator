from urllib.parse import urlparse


class MockLLMProvider:
    """Provides mock/fixture data for local testing without real LLM calls."""

    @staticmethod
    def mock_structured_data(url: str, pages: list) -> dict:
        domain = urlparse(url).netloc
        sections = [
            {
                "name": "Main",
                "pages": [
                    {"title": p.title, "url": p.url, "description": p.description or "Mock description"}
                    for p in pages[:10]
                ],
            },
        ]
        if len(pages) > 10:
            sections.append({
                "name": "Optional",
                "pages": [
                    {"title": p.title, "url": p.url, "description": p.description or "Mock description"}
                    for p in pages[10:]
                ],
            })
        return {
            "site_name": domain,
            "description": f"A website at {domain}.",
            "details": None,
            "sections": sections,
        }
