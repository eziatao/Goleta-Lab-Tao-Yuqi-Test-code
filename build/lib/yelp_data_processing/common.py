"""Shared validation and schema rules."""
import math
import re
from dataclasses import dataclass
from typing import Any


class DataError(ValueError):
    """Invalid input with an actionable explanation."""


@dataclass
class Table:
    columns: list[str]
    rows: list[dict[str, Any]]


def blank(value):
    return value is None or (isinstance(value, str) and not value.strip())


def review_id(value, sentence=False):
    if not isinstance(value, str):
        raise DataError(f"ID must be text, got {value!r}")
    value = value.strip()
    pattern = r"[0-9]+-[0-9]+(?:-[0-9]+)?" if sentence else r"[0-9]+-[0-9]+"
    if not re.fullmatch(pattern, value):
        raise DataError(f"Invalid ID {value!r}: expected year-review" + ("[-sentence]" if sentence else ""))
    return "-".join(value.split("-")[:2])


def id_sort_key(value):
    return tuple(int(part) for part in review_id(value).split("-"))


def require(table, columns):
    missing = set(columns) - set(table.columns)
    if missing:
        raise DataError(f"Missing columns: {', '.join(sorted(missing))}")


def unique_ids(table):
    require(table, ["ID"])
    seen = set()
    for row in table.rows:
        row["ID"] = review_id(row.get("ID"))
        if row["ID"] in seen:
            raise DataError(f"Duplicate review ID: {row['ID']}")
        seen.add(row["ID"])


def score(value, context):
    if isinstance(value, bool) or blank(value):
        raise DataError(f"Missing/invalid score at {context}: {value!r}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise DataError(f"Non-numeric score at {context}: {value!r}") from exc
    if not math.isfinite(result) or result < 0:
        raise DataError(f"Score must be finite and nonnegative at {context}: {value!r}")
    return result


def quad_numbers(columns):
    groups = {}
    for col in columns:
        if col.startswith("quads-"):
            match = re.fullmatch(r"quads-([1-9][0-9]*)-([1-4])", col)
            if not match:
                raise DataError(f"Malformed quad column: {col}")
            groups.setdefault(int(match[1]), set()).add(int(match[2]))
    for number, parts in groups.items():
        if parts != {1, 2, 3, 4}:
            raise DataError(f"Incomplete quad column group: quads-{number}")
    return sorted(groups)
