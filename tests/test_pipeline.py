import contextlib
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path

from openpyxl import load_workbook
from yelp_data_processing.common import DataError, Table
from yelp_data_processing.json_to_excel import aggregate_records, json_to_excel
from yelp_data_processing.data_indexing import index_table
from yelp_data_processing.data_filter import filter_table
from yelp_data_processing.sentiment_counting import count_sentiment
from yelp_data_processing.aspect_vector_creating import create_vectors
from yelp_data_processing.excel_io import read_excel, write_excel
from yelp_data_processing.analysis import analyze_table, query_table
from yelp_data_processing.pipeline import run_pipeline, discover_inputs
from yelp_data_processing.cli import main


def record(key="2019-1-1", quads=None):
    return {"ID": key, "sentence": "Review", "quads": [] if quads is None else quads}


def metadata(ids):
    return Table(["ID", "business_name", "Positive", "Negative", "Neutral", "date"], [{"ID": key, "business_name": "Cafe", "Positive": .8, "Negative": .1, "Neutral": .1, "date": "2019-01-01"} for key in ids])


class ProcessingTests(unittest.TestCase):
    def test_aggregate_preserves_source_order_and_all_quad_elements(self):
        table = aggregate_records([record("2019-3-2", [["b", "good", "service", "positive"]]), record("2019-3-1", [["a", "bad", "food", "negative"], ["c", "ok", "ambience", "neutral"]])])
        self.assertEqual(len(table.rows), 1)
        self.assertEqual(table.columns, ["ID"] + [f"quads-{n}-{p}" for n in range(1, 4) for p in range(1, 5)])
        self.assertEqual(table.rows[0]["ID"], "2019-3")
        self.assertEqual(table.rows[0]["quads-1-1"], "b")
        self.assertEqual(table.rows[0]["quads-2-4"], "negative")
        self.assertEqual(table.rows[0]["quads-3-3"], "ambience")
        self.assertNotIn("sentence", table.columns)

    def test_invalid_json_schema(self):
        for records in [{}, [record(quads=[[1, 2, 3]])], [record("bad")], [{"ID": "2019-1-1"}]]:
            with self.subTest(records=records), self.assertRaises(DataError):
                aggregate_records(records)

    def test_index_exact_match_and_lowercase_date(self):
        source = aggregate_records([record("2019-2-1"), record("2019-1-1")])
        meta = metadata(["2019-1", "2019-2"])
        meta.rows[1]["business_name"] = "Other"
        result = index_table(source, meta)
        self.assertEqual(result.rows[0]["business_name"], "Other")
        self.assertEqual(result.rows[0]["Date"].year, 2019)
        self.assertEqual(result.columns[-5:], ["business_name", "Positive", "Negative", "Neutral", "Date"])

    def test_missing_and_duplicate_metadata_id(self):
        for ids in [[], ["2019-1", "2019-1"], ["2019-2"]]:
            with self.subTest(ids=ids), self.assertRaises(DataError):
                index_table(aggregate_records([record()]), metadata(ids))

    def test_bad_metadata_fields(self):
        for name, value in [("Positive", None), ("Negative", -1), ("Neutral", float("nan")), ("Positive", "abc"), ("business_name", ""), ("date", "bad")]:
            meta = metadata(["2019-1"])
            meta.rows[0][name] = value
            with self.subTest(name=name, value=value), self.assertRaises(DataError):
                index_table(aggregate_records([record()]), meta)

    def test_threshold_19_20_and_natural_sort(self):
        rows = [{"ID": f"2019-{n}", "business_name": "Keep" if n <= 20 else "Drop"} for n in range(39, 0, -1)]
        result, counts = filter_table(Table(["ID", "business_name"], rows))
        self.assertEqual(counts, {"Keep": 20, "Drop": 19})
        self.assertEqual([r["ID"] for r in result.rows], [f"2019-{n}" for n in range(1, 21)])

    def test_sentiment_sign_and_ties(self):
        rows = [{"ID": f"2019-{i}", "Positive": p, "Negative": n, "Neutral": u} for i, (p, n, u) in enumerate([(.8, .1, .1), (.1, .7, .2), (.1, .2, .7), (.5, .5, .1), (0, 0, 0)], 1)]
        table = Table(["ID", "Positive", "Negative", "Neutral"], rows)
        result, ties = count_sentiment(table)
        self.assertEqual([r["sentiment"] for r in result.rows], [.8, -.7, 0, .5, 0])
        self.assertEqual(result.columns, ["ID", "sentiment"])
        self.assertEqual(ties, 2)
        self.assertEqual(count_sentiment(table, "negative")[0].rows[3]["sentiment"], -.5)

    def test_vectors_cancellation_neutral_and_missing(self):
        table = aggregate_records([record("2019-1-1", [["a", "b", "food", "positive"], ["a", "b", "food", "Negative"], ["a", "b", "service", "Neutral"]]), record("2019-2-1", [["a", "b", "food", "POSITIVE"]])])
        table.columns += ["sentiment", "business_name", "Date"]
        for row in table.rows: row.update(sentiment=0, business_name="Cafe", Date="2019-01-01")
        result, normalized = create_vectors(table)
        self.assertEqual([result.rows[0]["food"], result.rows[0]["service"]], [0, 0])
        self.assertEqual([result.rows[1]["food"], result.rows[1]["service"]], [1, 999])
        self.assertEqual(normalized, 0)

    def test_alias_unknown_polarity_and_collision(self):
        table = aggregate_records([record(quads=[["a", "b", "food", "negatives"]])])
        table.columns.extend(["sentiment", "business_name", "Date"])
        table.rows[0].update(business_name="Cafe", Date="2019-01-01")
        table.rows[0]["sentiment"] = 0
        self.assertEqual(create_vectors(table)[1], 1)
        self.assertEqual(create_vectors(table)[0].rows[0]["food"], -1)
        with self.assertRaises(DataError): create_vectors(table, True)
        table.rows[0]["quads-1-4"] = "unknown"
        with self.assertRaises(DataError): create_vectors(table)
        table.rows[0]["quads-1-3"] = "ID"
        with self.assertRaises(DataError): create_vectors(table)

    def test_query_and_analysis_ignore_999(self):
        table = Table(["ID", "business_name", "sentiment", "Date", "food"], [{"ID": "2019-1", "business_name": "A", "sentiment": -.9, "food": 0}, {"ID": "2019-2", "business_name": "A", "sentiment": .8, "food": 999}])
        self.assertEqual(query_table(table, business="A", limit=1)[1], 2)
        self.assertEqual(query_table(table, review_id="2019-3")[1], 0)
        result = analyze_table(table)
        self.assertEqual(result["aspects"]["food"]["net_count"], 0)
        self.assertEqual(result["aspects"]["food"]["involved_reviews"], 1)

    def test_blank_aspect_ignored_and_literal_null_preserved(self):
        table = aggregate_records([record(quads=[["a", "b", None, None], ["a", "b", "NULL", " Neutral "]])])
        table.columns.extend(["sentiment", "business_name", "Date"])
        table.rows[0].update(business_name="Cafe", Date="2019-01-01")
        table.rows[0]["sentiment"] = 0
        result, _ = create_vectors(table)
        self.assertEqual(result.rows[0]["NULL"], 0)
        self.assertEqual(result.columns[-1], "NULL")

    def test_incomplete_quad_columns_rejected(self):
        table = Table(["ID", "business_name", "Date", "sentiment", "quads-1-3"], [{"ID": "2019-1", "business_name": "Cafe", "Date": "2019-01-01", "sentiment": 0, "quads-1-3": "food"}])
        with self.assertRaises(DataError):
            create_vectors(table)

    def test_repeated_positive_aspect_accumulates(self):
        table = aggregate_records([record(quads=[["a", "b", "food", "positive"], ["c", "d", "food", "positive"]])])
        table.columns.extend(["sentiment", "business_name", "Date"])
        table.rows[0].update(business_name="Cafe", Date="2019-01-01")
        table.rows[0]["sentiment"] = 0
        self.assertEqual(create_vectors(table)[0].rows[0]["food"], 2)

    def test_final_schema_drops_quads_scores_and_extra_fields(self):
        table = aggregate_records([record(quads=[["food", "good", "food quality", "positive"]])])
        table.columns += ["business_name", "Date", "sentiment", "Positive", "Negative", "Neutral", "extra"]
        table.rows[0].update(business_name="Cafe", Date="2019-01-01", sentiment=.8,
                            Positive=.8, Negative=.1, Neutral=.1, extra="discard")
        result, _ = create_vectors(table)
        self.assertEqual(result.columns, ["ID", "business_name", "date", "sentiment", "food quality"])
        self.assertEqual(set(result.rows[0]), set(result.columns))
        self.assertEqual(result.rows[0]["date"], "2019-01-01")
        self.assertEqual(result.rows[0]["food quality"], 1)
        self.assertIn("quads-1-1", table.columns)

    def test_final_schema_accepts_lowercase_date(self):
        table = Table(["ID", "business_name", "date", "sentiment"],
                      [{"ID": "2019-1", "business_name": "Cafe", "date": "2019-01-01", "sentiment": 0}])
        result, _ = create_vectors(table)
        self.assertEqual(result.columns, ["ID", "business_name", "date", "sentiment"])
        self.assertEqual(result.rows[0], table.rows[0])

    def test_final_schema_conflicting_dates_and_reserved_aspect(self):
        table = aggregate_records([record(quads=[["a", "b", "date", "positive"]])])
        table.columns += ["business_name", "Date", "sentiment"]
        table.rows[0].update(business_name="Cafe", Date="2019-01-01", sentiment=0)
        with self.assertRaises(DataError):
            create_vectors(table)
        table.rows[0]["quads-1-3"] = "food"
        table.columns.append("date")
        table.rows[0]["date"] = "2020-01-01"
        with self.assertRaises(DataError):
            create_vectors(table)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(__file__).resolve().parents[1] / "test" / "unit" / self._testMethodName
        self.folder.mkdir(parents=True, exist_ok=True)

    def inputs(self, records=None):
        path = self.folder / "yelp-top300-final-0.7.json"
        path.write_text(json.dumps([record()] if records is None else records), encoding="utf-8-sig")
        meta = self.folder / "overall-sentimen.xlsx"
        write_excel(metadata(["2019-1"]), meta)
        return path, meta

    def test_full_file_pipeline_and_header_only_output(self):
        source, meta = self.inputs([record(quads=[["food", "good", "food quality", "positive"]])])
        report = run_pipeline(source, meta, self.folder / "out", min_count=1)
        self.assertEqual(report["status"], "complete")
        final = read_excel(self.folder / "out/yelp_data_processed.xlsx")
        self.assertEqual(final.rows[0]["food quality"], 1)
        self.assertEqual(final.rows[0]["sentiment"], .8)
        self.assertEqual(final.columns, ["ID", "business_name", "date", "sentiment", "food quality"])
        self.assertEqual(report["stages"]["aspect_vector_creating"]["aspect_columns"], ["food quality"])
        self.assertEqual(discover_inputs(self.folder), (source, meta))
        run_pipeline(source, meta, self.folder / "empty", min_count=20)
        self.assertEqual(read_excel(self.folder / "empty/yelp_data_processed.xlsx").rows, [])

    def test_empty_json(self):
        source, meta = self.inputs([])
        run_pipeline(source, meta, self.folder / "empty")
        self.assertEqual(read_excel(self.folder / "empty/yelp_data_processed.xlsx").rows, [])

    def test_excel_preserves_text_and_never_executes_formula(self):
        file = self.folder / "literal.xlsx"
        write_excel(Table(["ID", "value"], [{"ID": "2019-001", "value": "=1+1"}]), file)
        wb = load_workbook(file)
        self.assertEqual(wb.active["B2"].data_type, "s")
        self.assertEqual(wb.active["B2"].value, "=1+1")
        self.assertEqual(wb.active.freeze_panes, "B2")
        wb.close()
        self.assertEqual(read_excel(file).rows[0]["ID"], "2019-001")

    def test_failed_write_does_not_replace_existing_output(self):
        file = self.folder / "safe.xlsx"
        write_excel(Table(["ID"], [{"ID": "2019-1"}]), file)
        before = file.read_bytes()
        with self.assertRaises(DataError):
            write_excel(Table(["ID"], [{"ID": "x" * 32768}]), file)
        self.assertEqual(file.read_bytes(), before)

    def test_cli_installed_module_and_failure_exit(self):
        source, _ = self.inputs()
        result = subprocess.run([sys.executable, "-m", "yelp_data_processing", "json-to-excel", "--input", str(source), "--output", str(self.folder / "out.xlsx")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["output_reviews"], 1)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["data_filter", "--input", str(self.folder / "absent.xlsx"), "--output", str(self.folder / "bad.xlsx")]), 2)
            self.assertEqual(main(["json_to_excel", "--input", str(source), "--output", str(source)]), 2)


if __name__ == "__main__":
    unittest.main()
