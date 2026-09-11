"""Run tests and keep all generated files under the project's test directory."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, help="Also run and independently validate the real-data pipeline")
    parser.add_argument("--extension-input", type=Path, help="Run the extension on an existing processed workbook")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    output = project/"test"
    output.mkdir(parents=True, exist_ok=True)
    commands = [
        ("unit", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
        ("demo", [sys.executable, "scripts/demo.py"]),
    ]
    if args.data_dir:
        commands += [
            ("pipeline", [sys.executable, "-m", "yelp_data_processing", "run", "--data-dir", str(args.data_dir.resolve()), "--output-dir", str(output)]),
            ("query", [sys.executable, "-m", "yelp_data_processing", "query", "--input", str(output/"yelp_data_processed.xlsx"), "--id", "2019-3", "--output", str(output/"query_2019_3.xlsx")]),
            ("analysis", [sys.executable, "-m", "yelp_data_processing", "analyze", "--input", str(output/"yelp_data_processed.xlsx"), "--output", str(output/"analysis.json")]),
            ("independent_validation", [sys.executable, "scripts/validate_real.py", "--data-dir", str(args.data_dir.resolve()), "--output-dir", str(output)]),
        ]
    extension_input = args.extension_input.resolve() if args.extension_input else output/"yelp_data_processed.xlsx" if args.data_dir else None
    if extension_input:
        commands += [
            ("extension", [sys.executable, "-m", "yelp_data_processing", "extend", "--input", str(extension_input), "--output-dir", str(output)]),
            ("extension_validation", [sys.executable, "scripts/validate_extension.py", "--input", str(extension_input), "--output-dir", str(output)]),
        ]
    results = []
    for name, command in commands:
        print(f"Running {name}: {subprocess.list2cmdline(command)}", flush=True)
        with (output/f"{name}.log").open("w", encoding="utf-8") as log:
            process = subprocess.run(command, cwd=project, stdout=log, stderr=subprocess.STDOUT)
        results.append({"name": name, "command": subprocess.list2cmdline(command), "exit_code": process.returncode})
        (output/"test_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{name}: exit {process.returncode}; files saved in {output}", flush=True)
        if process.returncode:
            print((output/f"{name}.log").read_text(encoding="utf-8"))
            return process.returncode
    print("All tests passed. Every stage output remains in test/.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
