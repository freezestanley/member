import sys

sys.path.insert(0, "scripts")

from frontmatter_utils import (  # noqa: E402
    parse_frontmatter_text,
    split_frontmatter,
    upsert_frontmatter_fields,
)


def test_upsert_frontmatter_fields_preserves_body_and_complex_fields():
    content = (
        "---\n"
        "type: concept\n"
        "aliases: [old, alias]\n"
        "current_weight: 1.0\n"
        "---\n"
        "# Title\n"
        "Body with --- separator.\n"
    )

    updated = upsert_frontmatter_fields(
        content,
        {
            "current_weight": "2.5",
            "weight_schema_version": "2",
        },
    )

    prefix, fm_text, suffix = split_frontmatter(updated)
    assert prefix == "---\n"
    assert "aliases: [old, alias]" in fm_text
    assert "current_weight: 2.5" in fm_text
    assert "weight_schema_version: 2" in fm_text
    assert suffix == "---\n# Title\nBody with --- separator.\n"


def test_parse_frontmatter_text_keeps_scalar_values_as_strings():
    fm = parse_frontmatter_text(
        "status: \"archived\" # old\n"
        "importance: 3\n"
        "aliases: [a, b]\n"
    )

    assert fm["status"] == "\"archived\" # old"
    assert fm["importance"] == "3"
    assert fm["aliases"] == "[a, b]"
