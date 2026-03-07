from app.services.generator import assemble_markdown


def test_basic_assembly():
    data = {
        "site_name": "Example Corp",
        "summary": "A platform for building things.",
        "context": None,
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

    result = assemble_markdown(data)

    assert result.startswith("# Example Corp\n")
    assert "> A platform for building things." in result
    assert "## Docs" in result
    assert "- [Getting Started](https://example.com/docs/start): How to get started" in result


def test_assembly_with_context():
    data = {
        "site_name": "Test Site",
        "summary": "A test site.",
        "context": "This site has additional context.",
        "sections": [],
    }

    result = assemble_markdown(data)

    assert "# Test Site" in result
    assert "> A test site." in result
    assert "This site has additional context." in result


def test_assembly_no_description():
    data = {
        "site_name": "Minimal",
        "summary": None,
        "context": None,
        "sections": [
            {
                "name": "Pages",
                "pages": [
                    {"title": "Home", "url": "https://example.com", "description": ""},
                ],
            }
        ],
    }

    result = assemble_markdown(data)

    assert "- [Home](https://example.com)" in result
    assert ": " not in result.split("- [Home]")[1].split("\n")[0]
