"""Stage 1: sentence records to review-level, flattened quads."""
import json
from pathlib import Path

from .common import DataError, Table, review_id
from .excel_io import write_excel


def aggregate_records(records):
    if not isinstance(records, list):
        raise DataError("JSON root must be a list of objects")
    groups = {}
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict) or not {"sentence", "quads", "ID"} <= record.keys():
            raise DataError(f"Record {index}: expected sentence, quads and ID")
        if not isinstance(record["sentence"], str) or not isinstance(record["quads"], list):
            raise DataError(f"Record {index}: sentence must be text and quads must be a list")
        key = review_id(record["ID"], sentence=True)
        target = groups.setdefault(key, [])
        for quad in record["quads"]:
            if not isinstance(quad, list) or len(quad) != 4 or any(v is not None and not isinstance(v, str) for v in quad):
                raise DataError(f"Record {index}: each quad must contain exactly four text/null elements")
            target.append(quad)
    maximum = max((len(quads) for quads in groups.values()), default=0)
    columns = ["ID"] + [f"quads-{n}-{p}" for n in range(1, maximum + 1) for p in range(1, 5)]
    rows = []
    for key, quads in groups.items():
        row = {"ID": key}
        for n, quad in enumerate(quads, 1):
            row.update({f"quads-{n}-{p}": v for p, v in enumerate(quad, 1) if v is not None})
        rows.append(row)
    return Table(columns, rows)


def json_to_excel(input_path, output_path):
    records = json.loads(Path(input_path).read_text(encoding="utf-8-sig"))
    table = aggregate_records(records)
    write_excel(table, output_path)
    return {"input_sentences": len(records), "output_reviews": len(table.rows), "quad_columns": len(table.columns) - 1}
