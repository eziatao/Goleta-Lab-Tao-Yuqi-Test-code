"""Select up to ten aspects by number of non-999 reviews."""
from ..common import Table
from ..excel_io import read_excel, write_excel
from .schema import BASE_COLUMNS, aspect_columns, number


def filter_attributes(table):
    aspects = aspect_columns(table)
    counts = dict.fromkeys(aspects, 0)
    for row in table.rows:
        for name in aspects:
            counts[name] += number(row.get(name), f"{row['ID']}:{name}") != 999
    # Stable sort resolves ties using the original worksheet's column order.
    ranked = sorted(aspects, key=lambda name: -counts[name])
    selected = ranked[:10]
    rows = []
    for row in table.rows:
        new = {name: row.get(name) for name in BASE_COLUMNS}
        new.update({name: number(row.get(name), f"{row['ID']}:{name}") for name in selected})
        rows.append(new)
    return Table(BASE_COLUMNS + selected, rows), counts


def attribute_filter(input_path, output_path):
    result, counts = filter_attributes(read_excel(input_path))
    write_excel(result, output_path)
    selected = result.columns[len(BASE_COLUMNS):]
    return {"reviews": len(result.rows), "selected_aspects": selected,
            "non_999_counts": counts, "removed_aspects": [a for a in counts if a not in selected],
            "tie_rule": "original_column_order"}
