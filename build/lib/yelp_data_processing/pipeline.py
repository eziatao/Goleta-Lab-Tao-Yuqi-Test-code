"""File-based orchestration with per-stage progress and audit metrics."""
import json
import time
from pathlib import Path
from .common import DataError
from .json_to_excel import json_to_excel
from .data_indexing import data_indexing
from .data_filter import data_filter
from .sentiment_counting import sentiment_counting
from .aspect_vector_creating import aspect_vector_creating


def discover_inputs(data_dir):
    folder = Path(data_dir)
    def choose(names):
        for name in names:
            if (folder / name).is_file():
                return folder / name
        raise DataError(f"No input found in {folder}; expected one of {names}")
    return choose(["yelp-top300-final-0.7.json", "yelp-top300-final-0.7"]), choose(["overall-sentiment.xlsx", "overall-sentimen.xlsx"])


def run_pipeline(json_path, metadata_path, output_dir, min_count=20, tie_break="positive", strict_polarities=False, sheet=None, progress=None):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stages = [
        ("json_to_excel", "json_to_excel.xlsx", lambda dest: json_to_excel(json_path, dest)),
        ("data_indexing", "output.xlsx", lambda dest: data_indexing(output / "json_to_excel.xlsx", metadata_path, dest, sheet)),
        ("data_filter", "filted.xlsx", lambda dest: data_filter(output / "output.xlsx", dest, min_count)),
        ("sentiment_counting", "sentiment_counted.xlsx", lambda dest: sentiment_counting(output / "filted.xlsx", dest, tie_break)),
        ("aspect_vector_creating", "yelp_data_processed.xlsx", lambda dest: aspect_vector_creating(output / "sentiment_counted.xlsx", dest, strict_polarities)),
    ]
    targets = {str((output / name).resolve()).casefold() for _, name, _ in stages}
    for path in (json_path, metadata_path):
        if str(Path(path).resolve()).casefold() in targets:
            raise DataError("An input path overlaps a pipeline output")
    report = {"status": "running", "inputs": {"json": str(Path(json_path).resolve()), "metadata": str(Path(metadata_path).resolve())}, "stages": {}}
    manifest = output / "run_report.json"
    def save_report():
        temp = manifest.with_suffix(".json.tmp")
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(manifest)
    save_report()
    for name, filename, action in stages:
        if progress:
            progress(f"Starting {name}")
        started = time.perf_counter()
        try:
            details = action(output / filename)
        except Exception as exc:
            report.update(status="failed", failed_stage=name, error=str(exc))
            save_report()
            raise
        details.update(output=str((output / filename).resolve()), elapsed_seconds=round(time.perf_counter() - started, 3))
        report["stages"][name] = details
        save_report()
        if progress:
            progress(f"Finished {name}: {json.dumps(details, ensure_ascii=False)}")
    report["status"] = "complete"
    save_report()
    return report
