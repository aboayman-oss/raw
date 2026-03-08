"""Shared helpers for parsing and evaluating grade values."""

import re


def normalize_grade_text(value):
    if value is None:
        return ""
    return str(value).strip()


def grade_is_zero(value):
    text = normalize_grade_text(value)
    if not text:
        return False
    numerator = text.split("/", 1)[0].strip() if "/" in text else text
    match = re.search(r"-?\d+(?:\.\d+)?", numerator)
    if not match:
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return False
    try:
        return float(match.group()) == 0.0
    except ValueError:
        return False


def grade_missing_or_zero(value):
    text = normalize_grade_text(value)
    if not text:
        return True
    return grade_is_zero(text)