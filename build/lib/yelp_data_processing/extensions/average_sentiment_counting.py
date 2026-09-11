"""Mean sentiment of strictly preceding ten reviews, across all businesses."""
from collections import deque
from statistics import fmean

from ..common import DataError, Table, id_sort_key, require, unique_ids
from ..excel_io import read_excel, write_excel
from .schema import BASE_COLUMNS, number


def count_average_sentiment(table):
    require(table, BASE_COLUMNS + ["consistency", "business_aspect_consistency"])
    unique_ids(table)
    if "average_sentiment_10" in table.columns:
        raise DataError("Input already contains average_sentiment_10")
    ordered = sorted(table.rows, key=lambda row: (id_sort_key(row["ID"]), row["ID"]))
    history = deque(maxlen=10)
    rows = []
    for row in ordered:
        value = number(row.get("sentiment"), f"{row['ID']}:sentiment")
        rows.append(dict(row, average_sentiment_10=fmean(history) if history else None))
        history.append(value)
    return Table(table.columns + ["average_sentiment_10"], rows)


def average_sentiment_counting(input_path, output_path):
    result = count_average_sentiment(read_excel(input_path))
    write_excel(result, output_path)
    return {"reviews": len(result.rows), "window": 10, "include_current_row": False,
            "grouping": "entire_dataset", "first_row_average": "blank", "sort": "numeric ID segments"}
