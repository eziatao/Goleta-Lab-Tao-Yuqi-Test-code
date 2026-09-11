"""Stage 4: retain the strongest sentiment as a signed score."""
from .common import DataError, Table, require, score, unique_ids
from .excel_io import read_excel, write_excel

LABELS = ["Positive", "Negative", "Neutral"]


def count_sentiment(table, tie_break="positive"):
    require(table, ["ID", *LABELS])
    unique_ids(table)
    if "sentiment" in table.columns:
        raise DataError("Input already contains sentiment")
    first = tie_break.capitalize()
    if first not in LABELS:
        raise DataError(f"Unknown tie policy: {tie_break}")
    priority = [first] + [c for c in LABELS if c != first]
    columns = []
    for col in table.columns:
        if col in LABELS:
            if "sentiment" not in columns:
                columns.append("sentiment")
        else:
            columns.append(col)
    rows, ties = [], 0
    for row in table.rows:
        values = {name: score(row.get(name), f"{row['ID']}:{name}") for name in LABELS}
        winner = max(priority, key=values.get)
        ties += sum(v == values[winner] for v in values.values()) > 1
        new = {k: v for k, v in row.items() if k not in LABELS}
        new["sentiment"] = values[winner] if winner == "Positive" else -values[winner] if winner == "Negative" else 0
        rows.append(new)
    return Table(columns, rows), ties


def sentiment_counting(input_path, output_path, tie_break="positive"):
    result, ties = count_sentiment(read_excel(input_path), tie_break)
    write_excel(result, output_path)
    return {"reviews": len(result.rows), "ties": ties, "tie_break": tie_break}
