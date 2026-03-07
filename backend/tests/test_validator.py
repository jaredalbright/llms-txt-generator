from app.services.validator import validate_llms_txt


def test_valid_document():
    md = """# My Site

> A great site for things.

## Docs

- [Getting Started](https://example.com/start): How to begin
- [API Reference](https://example.com/api): Full API docs
"""
    issues = validate_llms_txt(md)
    assert len(issues) == 0


def test_missing_h1():
    md = """## Not an H1

> Summary

- [Link](https://example.com): desc
"""
    issues = validate_llms_txt(md)
    errors = [i for i in issues if i.severity == "error"]
    assert any("H1" in i.message for i in errors)


def test_missing_blockquote():
    md = """# My Site

## Docs

- [Link](https://example.com): desc
"""
    issues = validate_llms_txt(md)
    warnings = [i for i in issues if i.severity == "warning"]
    assert any("blockquote" in i.message for i in warnings)


def test_forbidden_h3():
    md = """# My Site

> Summary

### Not Allowed

- [Link](https://example.com): desc
"""
    issues = validate_llms_txt(md)
    errors = [i for i in issues if i.severity == "error"]
    assert any("H3" in i.message for i in errors)


def test_bad_link_format():
    md = """# My Site

> Summary

## Docs

- Just plain text, no link
"""
    issues = validate_llms_txt(md)
    warnings = [i for i in issues if i.severity == "warning"]
    assert any("format" in i.message.lower() for i in warnings)
