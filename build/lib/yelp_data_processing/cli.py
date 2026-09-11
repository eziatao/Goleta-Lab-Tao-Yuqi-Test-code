"""Public CLI. JSON on stdout; progress and errors on stderr."""
import argparse
import json
import sys
from pathlib import Path
from zipfile import BadZipFile
from . import __version__
from .common import DataError
from .excel_io import read_excel, write_excel
from .analysis import analyze_table, query_table
from .pipeline import discover_inputs, run_pipeline
from .json_to_excel import json_to_excel
from .data_indexing import data_indexing
from .data_filter import data_filter
from .sentiment_counting import sentiment_counting
from .aspect_vector_creating import aspect_vector_creating
from .extensions.attribute_filter import attribute_filter
from .extensions.business_consistency_counting import business_consistency_counting
from .extensions.average_sentiment_counting import average_sentiment_counting
from .extensions.pipeline import run_extension


def parser():
    root = argparse.ArgumentParser(description="Yelp aspect-level data processing")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run all five stages")
    run.add_argument("--data-dir", type=Path, default=Path("../data"))
    run.add_argument("--json", type=Path)
    run.add_argument("--metadata", type=Path)
    run.add_argument("--output-dir", type=Path, default=Path("outputs"))
    run.add_argument("--min-count", type=int, default=20)
    run.add_argument("--tie-break", choices=["positive", "negative", "neutral"], default="positive")
    run.add_argument("--strict-polarities", action="store_true")
    run.add_argument("--sheet")
    names = ["json_to_excel", "data_indexing", "data_filter", "sentiment_counting", "aspect_vector_creating"]
    for name in names:
        cmd = commands.add_parser(name, aliases=[name.replace("_", "-")])
        cmd.set_defaults(command=name)
        cmd.add_argument("--input", type=Path, required=True)
        cmd.add_argument("--output", type=Path, required=True)
        if name == "data_indexing":
            cmd.add_argument("--metadata", type=Path, required=True)
            cmd.add_argument("--sheet")
        if name == "data_filter":
            cmd.add_argument("--min-count", type=int, default=20)
        if name == "sentiment_counting":
            cmd.add_argument("--tie-break", choices=["positive", "negative", "neutral"], default="positive")
        if name == "aspect_vector_creating":
            cmd.add_argument("--strict-polarities", action="store_true")
    extend = commands.add_parser("extend", help="Run the three optional post-processing stages")
    extend.add_argument("--input", type=Path, required=True)
    extend.add_argument("--output-dir", type=Path, default=Path("outputs"))
    for name in ["attribute_filter", "business_consistency_counting", "average_sentiment_counting"]:
        cmd = commands.add_parser(name, aliases=[name.replace("_", "-")])
        cmd.set_defaults(command=name)
        cmd.add_argument("--input", type=Path, required=True)
        cmd.add_argument("--output", type=Path, required=True)
    query = commands.add_parser("query", help="Exact ID/business query, optionally export xlsx")
    query.add_argument("--input", type=Path, required=True)
    query.add_argument("--id")
    query.add_argument("--business")
    query.add_argument("--limit", type=int, default=20)
    query.add_argument("--output", type=Path)
    analysis = commands.add_parser("analyze", help="Summarize final data; exclude missing aspect sentinel 999")
    analysis.add_argument("--input", type=Path, required=True)
    analysis.add_argument("--output", type=Path)
    return root


def dispatch(args):
    cmd = args.command
    if cmd == "extend":
        return run_extension(args.input, args.output_dir, lambda message: print(message, file=sys.stderr, flush=True))
    if cmd == "run":
        if (args.json is None) != (args.metadata is None):
            raise DataError("Supply both --json and --metadata, or use --data-dir")
        if args.min_count < 1:
            raise DataError("min-count must be positive")
        json_path, metadata_path = (args.json, args.metadata) if args.json else discover_inputs(args.data_dir)
        return run_pipeline(json_path, metadata_path, args.output_dir, args.min_count, args.tie_break, args.strict_polarities, args.sheet, lambda message: print(message, file=sys.stderr, flush=True))
    if getattr(args, "output", None):
        inputs = [args.input, *([args.metadata] if cmd == "data_indexing" else [])]
        if args.output.resolve() in [p.resolve() for p in inputs]:
            raise DataError("Output must differ from input files")
    if cmd == "json_to_excel":
        return json_to_excel(args.input, args.output)
    if cmd == "data_indexing":
        return data_indexing(args.input, args.metadata, args.output, args.sheet)
    if cmd == "data_filter":
        return data_filter(args.input, args.output, args.min_count)
    if cmd == "sentiment_counting":
        return sentiment_counting(args.input, args.output, args.tie_break)
    if cmd == "aspect_vector_creating":
        return aspect_vector_creating(args.input, args.output, args.strict_polarities)
    if cmd == "attribute_filter":
        return attribute_filter(args.input, args.output)
    if cmd == "business_consistency_counting":
        return business_consistency_counting(args.input, args.output)
    if cmd == "average_sentiment_counting":
        return average_sentiment_counting(args.input, args.output)
    table = read_excel(args.input)
    if cmd == "query":
        result, matched = query_table(table, args.id, args.business, args.limit)
        if args.output:
            write_excel(result, args.output)
        return {"matched": matched, "returned": len(result.rows), "records": result.rows}
    report = analyze_table(table)
    if args.output:
        if args.output.suffix.lower() != ".json":
            raise DataError("Analysis output must use .json")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    try:
        report = dispatch(args)
    except (DataError, OSError, ValueError, BadZipFile) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0
