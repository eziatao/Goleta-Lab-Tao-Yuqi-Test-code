"""Column and value validation shared only by the extension."""
import math

from ..common import DataError, blank, require, unique_ids

BASE_COLUMNS = ["ID", "business_name", "date", "sentiment"]
DERIVED_COLUMNS = ["consistency", "business_aspect_consistency", "average_sentiment_10"]


def number(value, context):
    if isinstance(value, bool) or blank(value):
        raise DataError(f"Missing/invalid numeric value at {context}: {value!r}")
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise DataError(f"Non-numeric value at {context}: {value!r}") from exc
    if not math.isfinite(result):
        raise DataError(f"Value must be finite at {context}: {value!r}")
    return result


def aspect_columns(table):
    require(table, BASE_COLUMNS)
    unique_ids(table)
    columns = [c for c in table.columns if c not in BASE_COLUMNS + DERIVED_COLUMNS]
    if any(c.startswith("quads-") or c in {"Date", "Positive", "Negative", "Neutral"} for c in columns):
        raise DataError("Expected the compact yelp_data_processed.xlsx schema (lowercase date, no quads or raw sentiment columns)")
    return columns
