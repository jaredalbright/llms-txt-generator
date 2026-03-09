from app.services.url_utils import normalize_url, filter_junk_urls, score_url, rank_and_cap


class TestNormalizeUrl:
    def test_strips_fragment(self):
        assert normalize_url("https://example.com/page#section") == "https://example.com/page"

    def test_strips_tracking_params(self):
        result = normalize_url("https://example.com/page?utm_source=twitter&id=5")
        assert "utm_source" not in result
        assert "id=5" in result

    def test_lowercases_scheme_and_netloc(self):
        assert normalize_url("HTTPS://Example.COM/Path") == "https://example.com/Path"

    def test_removes_trailing_slash(self):
        assert normalize_url("https://example.com/docs/") == "https://example.com/docs"

    def test_preserves_root_slash(self):
        result = normalize_url("https://example.com/")
        assert result == "https://example.com/"

    def test_collapses_double_slashes(self):
        assert normalize_url("https://example.com//docs//page") == "https://example.com/docs/page"

    def test_strips_all_tracking_params(self):
        result = normalize_url("https://example.com?fbclid=abc&gclid=xyz&ref=foo")
        assert result == "https://example.com"


class TestFilterJunkUrls:
    def test_filters_login(self):
        urls = ["https://example.com/login", "https://example.com/docs"]
        result = filter_junk_urls(urls)
        assert result == ["https://example.com/docs"]

    def test_filters_admin(self):
        urls = ["https://example.com/admin", "https://example.com/about"]
        result = filter_junk_urls(urls)
        assert result == ["https://example.com/about"]

    def test_preserves_api_reference(self):
        urls = ["https://example.com/api-reference", "https://example.com/api-docs"]
        result = filter_junk_urls(urls)
        assert len(result) == 2

    def test_filters_api_endpoint(self):
        urls = ["https://example.com/api/v1/users", "https://example.com/docs"]
        result = filter_junk_urls(urls)
        assert result == ["https://example.com/docs"]

    def test_filters_file_extensions(self):
        urls = [
            "https://example.com/file.pdf",
            "https://example.com/style.css",
            "https://example.com/docs",
        ]
        result = filter_junk_urls(urls)
        assert result == ["https://example.com/docs"]

    def test_deduplicates(self):
        urls = [
            "https://example.com/docs",
            "https://example.com/docs/",
            "https://example.com/docs?utm_source=twitter",
        ]
        result = filter_junk_urls(urls)
        assert len(result) == 1

    def test_filters_pagination(self):
        urls = ["https://example.com/page/2", "https://example.com/blog"]
        result = filter_junk_urls(urls)
        assert result == ["https://example.com/blog"]

    def test_filters_wp_admin(self):
        urls = ["https://example.com/wp-admin/settings", "https://example.com/about"]
        result = filter_junk_urls(urls)
        assert result == ["https://example.com/about"]


class TestScoreUrl:
    def test_nav_source_highest(self):
        nav = score_url("https://example.com/docs", source="nav", depth=0, inlink_count=0)
        sitemap = score_url("https://example.com/docs", source="sitemap", depth=0, inlink_count=0)
        body = score_url("https://example.com/docs", source="body", depth=0, inlink_count=0)
        assert nav > sitemap > body

    def test_depth_penalty(self):
        shallow = score_url("https://example.com/docs", source="body", depth=0, inlink_count=0)
        deep = score_url("https://example.com/docs", source="body", depth=2, inlink_count=0)
        assert shallow > deep

    def test_inlink_bonus(self):
        few = score_url("https://example.com/docs", source="body", depth=0, inlink_count=1)
        many = score_url("https://example.com/docs", source="body", depth=0, inlink_count=5)
        assert many > few

    def test_inlink_capped_at_5(self):
        five = score_url("https://example.com/docs", source="body", depth=0, inlink_count=5)
        ten = score_url("https://example.com/docs", source="body", depth=0, inlink_count=10)
        assert five == ten

    def test_path_depth_penalty(self):
        shallow = score_url("https://example.com/docs", source="body", depth=0, inlink_count=0)
        deep_path = score_url("https://example.com/docs/api/v2/ref", source="body", depth=0, inlink_count=0)
        assert shallow > deep_path


class TestRankAndCap:
    def test_returns_top_n(self):
        metas = {
            "https://example.com/a": {"source": "nav", "depth": 0, "inlink_count": 5},
            "https://example.com/b": {"source": "body", "depth": 1, "inlink_count": 0},
            "https://example.com/c": {"source": "sitemap", "depth": 0, "inlink_count": 2},
        }
        result = rank_and_cap(metas, max_pages=2)
        assert len(result) == 2
        assert result[0] == "https://example.com/a"  # highest score

    def test_homepage_always_included(self):
        metas = {
            "https://example.com/": {"source": "body", "depth": 2, "inlink_count": 0},
            "https://example.com/a": {"source": "nav", "depth": 0, "inlink_count": 5},
            "https://example.com/b": {"source": "nav", "depth": 0, "inlink_count": 5},
        }
        result = rank_and_cap(metas, max_pages=2)
        assert "https://example.com/" in result
