"""Independent three-stage file pipeline for already processed Yelp data."""
import json
import time
from pathlib import Path

from ..common import DataError
from .attribute_filter import attribute_filter
from .business_consistency_counting import business_consistency_counting
from .average_sentiment_counting import average_sentiment_counting


def run_extension(input_path, output_dir, progress=None):
    folder = Path(output_dir)
    stages = [
        ("attribute_filter", "attribute_filter.xlsx", lambda dest: attribute_filter(input_path, dest)),
        ("business_consistency_counting", "business_consistency_counted.xlsx", lambda dest: business_consistency_counting(folder/"attribute_filter.xlsx", dest)),
        ("average_sentiment_counting", "yelp_data_processed_updated.xlsx", lambda dest: average_sentiment_counting(folder/"business_consistency_counted.xlsx", dest)),
    ]
    if Path(input_path).resolve() in [(folder/name).resolve() for _, name, _ in stages]:
        raise DataError("An extension output overlaps the input")
    folder.mkdir(parents=True, exist_ok=True)
    report = {"status": "running", "input": str(Path(input_path).resolve()), "stages": {}}
    manifest = folder/"extension_report.json"
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
            details = action(folder/filename)
        except Exception as exc:
            report.update(status="failed", failed_stage=name, error=str(exc))
            save_report()
            raise
        details.update(output=str((folder/filename).resolve()), elapsed_seconds=round(time.perf_counter()-started, 3))
        report["stages"][name] = details
        save_report()
        if progress:
            progress(f"Finished {name}: {len(report['stages'])}/3")
    report["status"] = "complete"
    save_report()
    return report
