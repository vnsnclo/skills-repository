#!/usr/bin/env python3
"""
Quick validation script for skills.

This intentionally performs only lightweight checks that are useful before
syncing local skills into a shared skills directory.
"""

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - depends on the local Python install
    yaml = None


MAX_SKILL_NAME_LENGTH = 64
ALLOWED_PROPERTIES = {"name", "description", "license", "allowed-tools", "metadata"}


class FrontmatterError(ValueError):
    """Raised when the fallback frontmatter parser cannot read the YAML."""


def parse_scalar(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_simple_frontmatter(frontmatter_text):
    """Parse simple top-level YAML frontmatter when PyYAML is unavailable."""
    frontmatter = {}
    lines = frontmatter_text.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            index += 1
            continue

        if line[0].isspace():
            index += 1
            continue

        match = re.match(r"^([A-Za-z0-9_-]+):(?:\s*(.*))?$", line)
        if not match:
            raise FrontmatterError(f"Invalid YAML frontmatter line: {line}")

        key = match.group(1)
        value = match.group(2) or ""

        if value in {"|", ">"}:
            block_lines = []
            index += 1
            while index < len(lines):
                block_line = lines[index]
                if block_line.strip() and not block_line[0].isspace():
                    break
                block_lines.append(block_line.strip())
                index += 1
            separator = "\n" if value == "|" else " "
            frontmatter[key] = separator.join(part for part in block_lines if part)
            continue

        frontmatter[key] = parse_scalar(value)
        index += 1

    return frontmatter


def load_frontmatter(frontmatter_text):
    if yaml is not None:
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as exc:
            return False, f"Invalid YAML in frontmatter: {exc}", None
    else:
        try:
            frontmatter = parse_simple_frontmatter(frontmatter_text)
        except FrontmatterError as exc:
            return False, str(exc), None

    if not isinstance(frontmatter, dict):
        return False, "Frontmatter must be a YAML dictionary", None

    return True, "", frontmatter


def validate_skill(skill_path):
    """Validate a single skill directory."""
    skill_path = Path(skill_path)

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"

    content = skill_md.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return False, "No YAML frontmatter found"

    match = re.match(r"^---\n(.*?)\n---(?:\n|$)", content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"

    ok, message, frontmatter = load_frontmatter(match.group(1))
    if not ok:
        return False, message

    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        allowed = ", ".join(sorted(ALLOWED_PROPERTIES))
        unexpected = ", ".join(sorted(unexpected_keys))
        return (
            False,
            f"Unexpected key(s) in SKILL.md frontmatter: {unexpected}. "
            f"Allowed properties are: {allowed}",
        )

    if "name" not in frontmatter:
        return False, "Missing 'name' in frontmatter"
    if "description" not in frontmatter:
        return False, "Missing 'description' in frontmatter"

    name = frontmatter.get("name", "")
    if not isinstance(name, str):
        return False, f"Name must be a string, got {type(name).__name__}"
    name = name.strip()
    if name:
        if not re.match(r"^[a-z0-9-]+$", name):
            return (
                False,
                f"Name '{name}' should be hyphen-case "
                "(lowercase letters, digits, and hyphens only)",
            )
        if name.startswith("-") or name.endswith("-") or "--" in name:
            return (
                False,
                f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens",
            )
        if len(name) > MAX_SKILL_NAME_LENGTH:
            return (
                False,
                f"Name is too long ({len(name)} characters). "
                f"Maximum is {MAX_SKILL_NAME_LENGTH} characters.",
            )

    description = frontmatter.get("description", "")
    if not isinstance(description, str):
        return False, f"Description must be a string, got {type(description).__name__}"
    description = description.strip()
    if description:
        if "<" in description or ">" in description:
            return False, "Description cannot contain angle brackets (< or >)"
        if len(description) > 1024:
            return (
                False,
                f"Description is too long ({len(description)} characters). "
                "Maximum is 1024 characters.",
            )

    return True, "Skill is valid!"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python quick_validate.py <skill_directory>")
        sys.exit(1)

    valid, result_message = validate_skill(sys.argv[1])
    print(result_message)
    sys.exit(0 if valid else 1)
