"""
Data Cleaner — normalizes raw scraped data before saving.
"""
import re

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")

def parse_number(value: str | int | float | None) -> float | None:
    """
    A number from a scraped cell, or None when the cell is empty or not a number.
    A printed "0" is a real zero; a blank, "-" or "N/A" is unknown (todo.md 1.3), never 0.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUMBER_RE.search(str(value).replace(",", ""))
    return float(match.group()) if match else None


def parse_int(value: str | int | float | None) -> int | None:
    number = parse_number(value)
    return int(number) if number is not None else None


def apportion(total: int | float | None, share: float | None) -> int | None:
    """`total * share`, or None when either is unknown."""
    if total is None or share is None:
        return None
    return int(total * share)


def percent(part: int | float | None, whole: int | float | None) -> float | None:
    """part / whole × 100, or None when either is unknown or whole is not positive."""
    if part is None or whole is None or whole <= 0:
        return None
    return round(part / whole * 100, 2)


def clean_amount(value: str | int | float | None) -> int | None:
    """
    Convert various amount formats to integer lakhs; None when there is no amount.
    Handles: "1,23,456", "1.23 Cr", "₹1234 Lakh", 1234.56
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip().lower()
    number = parse_number(text)
    if number is None:
        return None
    if "cr" in text:                        # crore → lakhs
        return int(number * 100)
    return int(number)                      # lakh notation or a plain number


def normalize_district_name(name: str) -> str:
    """Normalize district names for matching across different data sources."""
    return (
        name.upper()
        .strip()
        .replace("&", "AND")
        .replace("-", " ")
        .replace("  ", " ")
    )


def clean_percentage(value) -> float | None:
    """Extract percentage as float from various formats."""
    if value is None:
        return None
    text = str(value).replace("%", "").strip()
    try:
        return round(float(text), 2)
    except ValueError:
        return None
