from app.services.generator import assemble_base_markdown


def test_basic_assembly():
    data = {
        "site_name": "Example Corp",
        "description": "A platform for building things.",
        "details": None,
        "sections": [
            {
                "name": "Docs",
                "pages": [
                    {
                        "title": "Getting Started",
                        "url": "https://example.com/docs/start",
                        "description": "How to get started",
                    }
                ],
            }
        ],
    }

    result = assemble_base_markdown(data)

    assert result.startswith("# Example Corp\n")
    assert "> A platform for building things." in result
    assert "## Docs" in result
    assert "- [Getting Started](https://example.com/docs/start): How to get started" in result


def test_assembly_with_details():
    data = {
        "site_name": "Test Site",
        "description": "A test site.",
        "details": "This site has additional details.",
        "sections": [],
    }

    result = assemble_base_markdown(data)

    assert "# Test Site" in result
    assert "> A test site." in result
    assert "This site has additional details." in result


def test_assembly_no_description():
    data = {
        "site_name": "Minimal",
        "description": None,
        "details": None,
        "sections": [
            {
                "name": "Pages",
                "pages": [
                    {"title": "Home", "url": "https://example.com", "description": ""},
                ],
            }
        ],
    }

    result = assemble_base_markdown(data)

    assert "- [Home](https://example.com)" in result
    assert ": " not in result.split("- [Home]")[1].split("\n")[0]
