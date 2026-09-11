"""Population standard deviation per review and mean per business."""
from collections import defaultdict
from statistics import fmean, pstdev

from ..common import DataError, Table, blank
from ..excel_io import read_excel, write_excel
from .schema import aspect_columns, number


def count_business_consistency(table):
    aspects = aspect_columns(table)
    if len(aspects) > 10:
        raise DataError("Run attribute_filter first: consistency expects at most ten aspects")
    if any(c in table.columns for c in ["consistency", "business_aspect_consistency", "average_sentiment_10"]):
        raise DataError("Input already contains extension statistics")
    rows = []
    groups = defaultdict(list)
    empty = 0
    for row in table.rows:
        business = row.get("business_name")
        if not isinstance(business, str) or blank(business):
            raise DataError(f"Missing business_name at {row['ID']}")
        values = [number(row.get(a), f"{row['ID']}:{a}") for a in aspects]
        values = [value for value in values if value != 999]
        consistency = pstdev(values) if values else None
        if consistency is None:
            empty += 1
        else:
            groups[business].append(consistency)
        rows.append(dict(row, consistency=consistency))
    means = {name: fmean(values) for name, values in groups.items()}
    for row in rows:
        row["business_aspect_consistency"] = means.get(row["business_name"])
    result = Table(table.columns + ["consistency", "business_aspect_consistency"], rows)
    return result, {"reviews": len(rows), "businesses": len({r["business_name"] for r in rows}),
                    "empty_consistency_reviews": empty, "standard_deviation": "population (ddof=0)",
                    "sentinel_999": "excluded", "empty_values": "blank, excluded from business mean"}


def business_consistency_counting(input_path, output_path):
    result, report = count_business_consistency(read_excel(input_path))
    write_excel(result, output_path)
    return report
