import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

from yelp_data_processing.common import DataError, Table
from yelp_data_processing.excel_io import read_excel, write_excel
from yelp_data_processing.analysis import analyze_table
from yelp_data_processing.extensions.schema import BASE_COLUMNS
from yelp_data_processing.extensions.attribute_filter import filter_attributes
from yelp_data_processing.extensions.business_consistency_counting import count_business_consistency
from yelp_data_processing.extensions.average_sentiment_counting import count_average_sentiment


def fixture():
    aspects = [f"aspect_{i:02}" for i in range(1, 13)]
    rows = []
    for i in range(14):
        row = {"ID": f"2020-{i+1}", "business_name": "A" if i % 2 == 0 else "B", "date": "2020-01-01", "sentiment": i-6}
        row.update({a: 999 for a in aspects})
        if i == 1:
            row[aspects[0]] = 0
        if i >= 2:
            row.update({a: (i+j) % 5 - 2 for j, a in enumerate(aspects[:10])})
        if i == 2:
            row.update({a: 10 for a in aspects[10:]})
        rows.append(row)
    return Table(BASE_COLUMNS + aspects, rows[::-1])


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(__file__).resolve().parents[1]/"test"/"extension_unit"/self._testMethodName
        self.folder.mkdir(parents=True, exist_ok=True)

    def command(self, *args):
        completed = subprocess.run([sys.executable, "-m", "yelp_data_processing", *map(str, args)], text=True, encoding="utf-8", capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_top_ten_counts_zero_negative_and_stable_ties(self):
        result, counts = filter_attributes(fixture())
        self.assertEqual(result.columns, BASE_COLUMNS + [f"aspect_{i:02}" for i in range(1, 11)])
        self.assertEqual(counts["aspect_01"], 13)
        self.assertEqual(counts["aspect_02"], 12)
        self.assertEqual(counts["aspect_11"], 1)
        self.assertEqual(result.rows[0]["ID"], "2020-14")
        self.assertEqual(set(result.rows[0]), set(result.columns))

    def test_small_and_empty_vocabularies(self):
        for count in [0, 2, 10, 12]:
            table = Table(BASE_COLUMNS + [f"a{i}" for i in range(count)], [])
            filtered, _ = filter_attributes(table)
            self.assertEqual(len(filtered.columns), 4 + min(count, 10))
            consistency, _ = count_business_consistency(filtered)
            self.assertEqual(count_average_sentiment(consistency).rows, [])

    def test_population_sd_missing_singleton_and_group_mean(self):
        rows = []
        for i, (business, a, b) in enumerate([("A", 1, 3), ("A", 999, 5), ("A", 999, 999), ("B", 999, 999)], 1):
            rows.append(dict(ID=f"2020-{i}", business_name=business, date="2020-01-01", sentiment=0, a=a, b=b))
        result, report = count_business_consistency(Table(BASE_COLUMNS + ["a", "b"], rows))
        self.assertEqual([r["consistency"] for r in result.rows], [1, 0, None, None])
        self.assertEqual([r["business_aspect_consistency"] for r in result.rows], [.5, .5, .5, None])
        self.assertEqual(report["empty_consistency_reviews"], 2)

    def test_consistency_signed_values(self):
        table = Table(BASE_COLUMNS + ["a", "b", "c"], [dict(ID="2020-1", business_name="A", date="2020-01-01", sentiment=0, a=-1, b=0, c=1)])
        result, _ = count_business_consistency(table)
        self.assertAlmostEqual(result.rows[0]["consistency"], math.sqrt(2/3))

    def test_average_uses_only_previous_ten_across_businesses(self):
        filtered, _ = filter_attributes(fixture())
        counted, _ = count_business_consistency(filtered)
        result = count_average_sentiment(counted)
        self.assertEqual([r["ID"] for r in result.rows], [f"2020-{i}" for i in range(1, 15)])
        self.assertIsNone(result.rows[0]["average_sentiment_10"])
        self.assertEqual(result.rows[1]["average_sentiment_10"], -6)
        for i, row in enumerate(result.rows[1:], 1):
            previous = [j-6 for j in range(max(0, i-10), i)]
            self.assertEqual(row["average_sentiment_10"], sum(previous)/len(previous))
        self.assertEqual(result.rows[11]["average_sentiment_10"], -.5)
        self.assertEqual(result.rows[13]["average_sentiment_10"], 1.5)

    def test_invalid_aspect_values(self):
        for value in [None, "", "bad", float("nan"), float("inf"), True]:
            table = fixture()
            table.rows[0]["aspect_01"] = value
            with self.subTest(value=value), self.assertRaises(DataError):
                filter_attributes(table)

    def test_duplicate_ids_missing_columns_and_unfiltered_input(self):
        table = fixture()
        table.rows.append(table.rows[0].copy())
        with self.assertRaises(DataError): filter_attributes(table)
        with self.assertRaises(DataError): count_business_consistency(fixture())
        with self.assertRaises(DataError): filter_attributes(Table(["ID"], []))

    def test_updated_analysis_excludes_derived_statistics(self):
        table, _ = filter_attributes(fixture())
        table, _ = count_business_consistency(table)
        table = count_average_sentiment(table)
        report = analyze_table(table)
        self.assertEqual(list(report["aspects"]), table.columns[4:14])

    def test_extension_cli_saves_each_step_and_preserves_source(self):
        source = self.folder/"yelp_data_processed.xlsx"
        write_excel(fixture(), source)
        before = source.read_bytes()
        report = self.command("extend", "--input", source, "--output-dir", self.folder)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(source.read_bytes(), before)
        for file in ["attribute_filter.xlsx", "business_consistency_counted.xlsx", "yelp_data_processed_updated.xlsx"]:
            self.assertTrue((self.folder/file).is_file())
        final = read_excel(self.folder/"yelp_data_processed_updated.xlsx")
        self.assertEqual(len(final.columns), 17)
        self.assertEqual(len(final.rows), 14)
        self.assertIsNone(final.rows[0].get("consistency"))
        self.assertIsNone(final.rows[0].get("average_sentiment_10"))
        self.assertEqual(final.rows[1]["consistency"], 0)
        self.assertEqual(final.rows[-1]["average_sentiment_10"], 1.5)
        self.assertEqual(self.command("query", "--input", self.folder/"yelp_data_processed_updated.xlsx", "--id", "2020-1")["matched"], 1)

    def test_individual_extension_commands(self):
        source = self.folder/"source.xlsx"
        write_excel(fixture(), source)
        self.command("attribute-filter", "--input", source, "--output", self.folder/"attribute_filter.xlsx")
        self.command("business_consistency_counting", "--input", self.folder/"attribute_filter.xlsx", "--output", self.folder/"business_consistency_counted.xlsx")
        self.command("average-sentiment-counting", "--input", self.folder/"business_consistency_counted.xlsx", "--output", self.folder/"yelp_data_processed_updated.xlsx")
        self.assertEqual(len(read_excel(self.folder/"yelp_data_processed_updated.xlsx").rows), 14)

    def test_original_five_cli_commands_still_work(self):
        source = self.folder/"source.json"
        source.write_text(json.dumps([{"ID": "2020-1-1", "sentence": "Good", "quads": [["food", "good", "food quality", "positive"]]}]), encoding="utf-8")
        meta = self.folder/"metadata.xlsx"
        write_excel(Table(["ID", "business_name", "Positive", "Negative", "Neutral", "Date"], [dict(ID="2020-1", business_name="A", Positive=.8, Negative=.1, Neutral=.1, Date="2020-01-01")]), meta)
        self.command("json_to_excel", "--input", source, "--output", self.folder/"json_to_excel.xlsx")
        self.command("data_indexing", "--input", self.folder/"json_to_excel.xlsx", "--metadata", meta, "--output", self.folder/"output.xlsx")
        self.command("data_filter", "--input", self.folder/"output.xlsx", "--output", self.folder/"filted.xlsx", "--min-count", 1)
        self.command("sentiment_counting", "--input", self.folder/"filted.xlsx", "--output", self.folder/"sentiment_counted.xlsx")
        self.command("aspect_vector_creating", "--input", self.folder/"sentiment_counted.xlsx", "--output", self.folder/"yelp_data_processed.xlsx")
        self.assertEqual(read_excel(self.folder/"yelp_data_processed.xlsx").rows[0]["food quality"], 1)

    def test_overlapping_input_and_output_rejected(self):
        source = self.folder/"attribute_filter.xlsx"
        write_excel(fixture(), source)
        before = source.read_bytes()
        completed = subprocess.run([sys.executable, "-m", "yelp_data_processing", "extend", "--input", str(source), "--output-dir", str(self.folder)], capture_output=True)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
