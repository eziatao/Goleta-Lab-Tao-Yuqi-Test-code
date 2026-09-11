"""Generate deterministic data and exercise the installed CLI end to end."""
import json
import subprocess
import sys
from pathlib import Path

from yelp_data_processing.common import Table
from yelp_data_processing.excel_io import read_excel, write_excel


def main():
    folder = Path(__file__).resolve().parents[1] / "test" / "demo"
    folder.mkdir(parents=True, exist_ok=True)
    records, metadata = [], []
    for n in range(1, 40):
        records.append({"ID": f"2019-{n}-1", "sentence": "Great food", "quads": [["food", "great", "food quality", "Positive"]]})
        metadata.append({"ID": f"2019-{n}", "business_name": "Keep Cafe" if n <= 20 else "Drop Cafe", "Positive": .8, "Negative": .1, "Neutral": .1, "Date": "2019-01-01"})
    records.append({"ID": "2019-1-2", "sentence": "Bad food, neutral service", "quads": [["food", "bad", "food quality", "Negative"], ["service", "ok", "service general", "Neutral"]]})
    source = folder / "source.json"
    source.write_text(json.dumps(records), encoding="utf-8")
    metadata_path = folder / "metadata.xlsx"
    write_excel(Table(["ID", "business_name", "Positive", "Negative", "Neutral", "Date"], metadata), metadata_path)
    log = []
    def run(*args):
        command = [sys.executable, "-m", "yelp_data_processing", *map(str, args)]
        completed = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, check=True)
        log.append({"command": subprocess.list2cmdline(command), "exit_code": completed.returncode, "result": json.loads(completed.stdout)})
        return log[-1]["result"]
    result = run("run", "--json", source, "--metadata", metadata_path, "--output-dir", folder)
    final = folder / "yelp_data_processed.xlsx"
    assert result["stages"]["data_filter"]["retained_reviews"] == 20
    query = run("query", "--input", final, "--id", "2019-1", "--output", folder / "query.xlsx")
    assert query["matched"] == 1
    assert query["records"][0]["food quality"] == 0
    assert query["records"][0]["service general"] == 0
    analysis = run("analyze", "--input", final, "--output", folder / "analysis.json")
    assert analysis["reviews"] == 20 and analysis["businesses"] == 1
    assert analysis["aspects"]["food quality"]["net_count"] == 19
    assert analysis["aspects"]["service general"]["missing_reviews"] == 19
    assert len(read_excel(folder / "query.xlsx").rows) == 1
    (folder / "demo_report.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "passed", "source_sentences": len(records), "reviews_before_filter": 39, "reviews_after_filter": 20, "report": str(folder / "demo_report.json")}, indent=2))


if __name__ == "__main__":
    main()
