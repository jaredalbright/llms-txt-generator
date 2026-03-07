import re
from app.models import ValidationIssue


def validate_llms_txt(markdown: str) -> list[ValidationIssue]:
    """
    Check a Markdown string for llms.txt spec compliance.

    Checks:
    1. Must start with H1 (# Site Name)
    2. Should have a blockquote summary (> ...)
    3. No H2 before any body text/blockquote
    4. H2 sections should contain link lists
    5. Links should be in [name](url) format
    6. No H3+ headings allowed
    """
    issues: list[ValidationIssue] = []
    lines = markdown.strip().split("\n")

    if not lines:
        issues.append(ValidationIssue(line=1, severity="error", message="File is empty"))
        return issues

    # Check H1
    if not lines[0].startswith("# ") or lines[0].startswith("## "):
        issues.append(ValidationIssue(
            line=1,
            severity="error",
            message="File must start with an H1 heading (# Site Name)"
        ))

    # Check for blockquote
    has_blockquote = any(line.strip().startswith("> ") for line in lines)
    if not has_blockquote:
        issues.append(ValidationIssue(
            line=2,
            severity="warning",
            message="Missing blockquote summary (> description)"
        ))

    # Check for forbidden headings (H3+)
    for i, line in enumerate(lines):
        if re.match(r'^#{3,}\s', line):
            issues.append(ValidationIssue(
                line=i + 1,
                severity="error",
                message="H3+ headings are not allowed in llms.txt"
            ))

    # Check link format in list items
    link_pattern = re.compile(r'^-\s+\[.+\]\(https?://.+\)')
    in_section = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            in_section = True
            continue
        if in_section and line.strip().startswith("- "):
            if not link_pattern.match(line.strip()):
                issues.append(ValidationIssue(
                    line=i + 1,
                    severity="warning",
                    message="List item should be in format: - [Title](url): description"
                ))

    return issues
