"""Format Paprika recipes as HTML for calendar event descriptions."""

from __future__ import annotations

import re
from html import escape
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .api import Recipe

# Paprika marks section headers either with markdown bold ("**SAUCE:**") or as
# an all-caps line ending in a colon ("PREPARE DRESSING:").
_BOLD_HEADER = re.compile(r"^\*\*(.+?)\*\*$")
_CAPS_HEADER = re.compile(r"^[^a-z]+:$")


def _header_text(line: str) -> str | None:
    """Return the header text if this line is a section header, else None."""
    if match := _BOLD_HEADER.match(line):
        return match.group(1)
    if _CAPS_HEADER.match(line) and any(c.isalpha() for c in line):
        return line
    return None


def _lines(text: str | list[str]) -> list[str]:
    """Split a Paprika text field into non-empty, stripped lines."""
    raw = text if isinstance(text, list) else text.splitlines()
    return [line.strip() for line in raw if line and line.strip()]


def _format_ingredients(ingredients: str) -> str:
    parts: list[str] = []
    items: list[str] = []

    def flush() -> None:
        if items:
            parts.append("<ul>" + "".join(items) + "</ul>")
            items.clear()

    for line in _lines(ingredients):
        if (header := _header_text(line)) is not None:
            flush()
            parts.append(f"<p><b>{escape(header)}</b></p>")
        else:
            items.append(f"<li>{escape(line)}</li>")
    flush()
    return "".join(parts)


def _format_directions(directions: str) -> str:
    parts: list[str] = []
    steps: list[str] = []

    def flush() -> None:
        if steps:
            parts.append("<ol>" + "".join(steps) + "</ol>")
            steps.clear()

    for line in _lines(directions):
        if (header := _header_text(line)) is not None:
            flush()
            parts.append(f"<p><b>{escape(header)}</b></p>")
        else:
            steps.append(f"<li>{escape(line)}</li>")
    flush()
    return "".join(parts)


def format_recipe_html(recipe: Recipe) -> str:
    """Build an HTML description: times, ingredients, directions, notes, source link."""
    sections: list[str] = []

    facts = [
        f"{label}: {escape(value)}"
        for label, value in (
            ("Prep", recipe.get("prep_time")),
            ("Cook", recipe.get("cook_time")),
            ("Total", recipe.get("total_time")),
        )
        if value
    ]
    if servings := recipe.get("servings"):
        facts.append(escape(servings))
    if facts:
        sections.append(f"<p>{' · '.join(facts)}</p>")

    if ingredients := _format_ingredients(recipe.get("ingredients") or ""):
        sections.append(f"<h3>Ingredients</h3>{ingredients}")

    if directions := _format_directions(recipe.get("directions") or ""):
        sections.append(f"<h3>Directions</h3>{directions}")

    if notes := (recipe.get("notes") or "").strip():
        sections.append(
            "<h3>Notes</h3><p>" + escape(notes).replace("\n", "<br>") + "</p>"
        )

    source_url = recipe.get("source_url") or ""
    if source_url.startswith(("http://", "https://")):
        label = escape(recipe.get("source") or "Original recipe")
        sections.append(
            f'<p><a href="{escape(source_url, quote=True)}" target="_blank">'
            f"{label}</a></p>"
        )

    return "".join(sections)
