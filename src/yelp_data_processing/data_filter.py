"""Stage 3: review counts per business and natural ID ordering."""
from collections import Counter

from .common import DataError, Table, blank, id_sort_key, require, unique_ids
from .excel_io import read_excel, write_excel


def filter_table(table, min_count=20):
    if isinstance(min_count, bool) or not isinstance(min_count, int) or min_count < 1:
        raise DataError("min_count must be a positive integer")
    require(table, ["ID", "business_name"])
    unique_ids(table)
    if any(blank(r.get("business_name")) for r in table.rows):
        raise DataError("Cannot group rows with missing business_name")
    counts = Counter(r["business_name"] for r in table.rows)
    rows = [r for r in table.rows if counts[r["business_name"]] >= min_count]
    rows.sort(key=lambda r: (id_sort_key(r["ID"]), r["ID"]))
    return Table(table.columns[:], rows), counts


def data_filter(input_path, output_path, min_count=20):
    table = read_excel(input_path)
    result, counts = filter_table(table, min_count)
    write_excel(result, output_path)
    return {"input_reviews": len(table.rows), "retained_reviews": len(result.rows), "removed_reviews": len(table.rows) - len(result.rows), "retained_businesses": sum(n >= min_count for n in counts.values()), "removed_businesses": sum(n < min_count for n in counts.values()), "min_count": min_count}
