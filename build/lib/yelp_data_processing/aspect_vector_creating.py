"""Stage 5: signed aspect counts with 999 exclusively for absence."""
from .common import DataError, Table, blank, quad_numbers, require, unique_ids
from .excel_io import read_excel, write_excel

FINAL_COLUMNS = ["ID", "business_name", "date", "sentiment"]


def create_vectors(table, strict_polarities=False):
    require(table, ["ID", "business_name", "sentiment"])
    date_column = "date" if "date" in table.columns else "Date"
    require(table, [date_column])
    if "date" in table.columns and "Date" in table.columns:
        if any(row.get("date") != row.get("Date") for row in table.rows):
            raise DataError("Conflicting date/Date columns")
    unique_ids(table)
    numbers = quad_numbers(table.columns)
    aspects = {}
    counts_per_row = []
    normalized = 0
    for row in table.rows:
        counts = {}
        for n in numbers:
            aspect = row.get(f"quads-{n}-3")
            if blank(aspect):
                continue
            if not isinstance(aspect, str):
                raise DataError(f"Aspect must be text at {row['ID']}, quad {n}")
            aspect = aspect.strip()
            if aspect in table.columns or aspect in FINAL_COLUMNS or aspect in {"Date", "Positive", "Negative", "Neutral"} or aspect.startswith("quads-"):
                raise DataError(f"Aspect name collides with an existing column: {aspect!r}")
            raw = row.get(f"quads-{n}-4")
            polarity = raw.strip().lower() if isinstance(raw, str) else ""
            if polarity == "negatives" and not strict_polarities:
                polarity = "negative"
                normalized += 1
            if polarity not in ("positive", "negative", "neutral"):
                raise DataError(f"Unknown polarity {raw!r} at {row['ID']}, quad {n}")
            counts[aspect] = counts.get(aspect, 0) + {"positive": 1, "negative": -1, "neutral": 0}[polarity]
            aspects.setdefault(aspect, None)
        if 999 in counts.values():
            raise DataError(f"Aspect count equals reserved missing sentinel 999 at {row['ID']}")
        counts_per_row.append(counts)
    rows = []
    for row, counts in zip(table.rows, counts_per_row):
        result = {"ID": row["ID"], "business_name": row.get("business_name"),
                  "date": row.get(date_column), "sentiment": row.get("sentiment")}
        result.update({a: counts.get(a, 999) for a in aspects})
        rows.append(result)
    return Table(FINAL_COLUMNS + list(aspects), rows), normalized


def aspect_vector_creating(input_path, output_path, strict_polarities=False):
    table = read_excel(input_path)
    result, normalized = create_vectors(table, strict_polarities)
    write_excel(result, output_path)
    return {"reviews": len(result.rows), "aspect_columns": result.columns[len(FINAL_COLUMNS):], "normalized_negatives": normalized}
