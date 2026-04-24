"""
Data Cleaner — normalizes raw scraped data before saving.
"""
import re


def clean_amount(value: str | int | float | None) -> int:
    """
    Convert various amount formats to integer lakhs.
    Handles: "1,23,456", "1.23 Cr", "₹1234 Lakh", 1234.56
    """
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)

    text = str(value).strip()
    text = text.replace("₹", "").replace(",", "").strip()

    # Handle crore notation → convert to lakhs
    if "cr" in text.lower():
        num = re.sub(r"[^\d.]", "", text)
        return int(float(num) * 100) if num else 0

    # Handle lakh notation
    if "lakh" in text.lower() or "lac" in text.lower():
        num = re.sub(r"[^\d.]", "", text)
        return int(float(num)) if num else 0

    # Plain number
    num = re.sub(r"[^\d.]", "", text)
    return int(float(num)) if num else 0


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
