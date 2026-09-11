"""Stage 2: exact, validated review-ID metadata join."""
from datetime import date, datetime

from .common import DataError, Table, blank, require, score, unique_ids
from .excel_io import read_excel, write_excel

METADATA = ["business_name", "Positive", "Negative", "Neutral", "Date"]


def index_table(table, metadata):
    unique_ids(table)
    unique_ids(metadata)
    require(metadata, METADATA[:-1])
    date_column = "Date" if "Date" in metadata.columns else "date"
    require(metadata, [date_column])
    if set(METADATA) & set(table.columns):
        raise DataError("Input already contains indexing columns")
    lookup = {row["ID"]: row for row in metadata.rows}
    missing = [row["ID"] for row in table.rows if row["ID"] not in lookup]
    if missing:
        raise DataError(f"{len(missing)} IDs have no metadata match; examples: {missing[:5]}")
    output = []
    for row in table.rows:
        source = lookup[row["ID"]]
        business = source.get("business_name")
        if not isinstance(business, str) or blank(business):
            raise DataError(f"Missing business_name at {row['ID']}")
        value = source.get(date_column)
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.strip())
            except ValueError as exc:
                raise DataError(f"Invalid ISO Date at {row['ID']}: {value!r}") from exc
        if not isinstance(value, (date, datetime)) or (isinstance(value, datetime) and value.tzinfo is not None):
            raise DataError(f"Date must be an Excel date or timezone-free ISO date at {row['ID']}")
        if "Date" in metadata.columns and "date" in metadata.columns and source.get("Date") != source.get("date"):
            raise DataError(f"Conflicting Date/date columns at {row['ID']}")
        new = dict(row, business_name=business, Date=value)
        for name in ["Positive", "Negative", "Neutral"]:
            new[name] = score(source.get(name), f"{row['ID']}:{name}")
        output.append(new)
    return Table(table.columns + METADATA, output)


def data_indexing(input_path, metadata_path, output_path, sheet=None):
    table = read_excel(input_path)
    metadata = read_excel(metadata_path, sheet, selected=["ID", *METADATA, "date"])
    result = index_table(table, metadata)
    write_excel(result, output_path)
    return {"matched_reviews": len(result.rows), "metadata_rows": len(metadata.rows), "unmatched_reviews": 0}
