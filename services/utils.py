"""Shared utility functions for SAHAYAK SOS services."""


def contains_keyword(text, keyword):
    """
    Check if a keyword exists as a whole word/phrase in text.
    Uses word boundary matching to avoid partial matches.
    """
    normalized_keyword = " ".join(keyword.casefold().split())
    start = text.find(normalized_keyword)
    while start != -1:
        end = start + len(normalized_keyword)
        before = text[start - 1] if start else ""
        after = text[end] if end < len(text) else ""
        if (not before or not before.isalnum()) and (not after or not after.isalnum()):
            return True
        start = text.find(normalized_keyword, start + 1)
    return False


def add_unique(items, value):
    """Add a value to a list only if it's not already present."""
    if value not in items:
        items.append(value)
