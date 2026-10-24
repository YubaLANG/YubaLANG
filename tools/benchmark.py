"""Measure YubaLANG startup, function, arithmetic, and collection workloads."""

import argparse
import contextlib
import io
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parent.parent
INTERPRETER = ROOT / "YubaLANG.py"
sys.path.insert(0, str(ROOT))

from lang.interpreter import run_file


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _measure(source_path: Path, runs: int) -> list[float]:
    command = [sys.executable, str(INTERPRETER), str(source_path)]
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, timeout=60)

    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        subprocess.run(command, cwd=ROOT, check=True, capture_output=True, timeout=60)
        samples.append(time.perf_counter() - start)
    return samples


def _measure_peak_traced_bytes(source_path: Path) -> int:
    driver = (
        "import sys, tracemalloc; tracemalloc.start(); "
        "from lang.interpreter import run_file; run_file(sys.argv[1]); "
        "print('__YUBALANG_PEAK__' + str(tracemalloc.get_traced_memory()[1]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", driver, str(source_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    marker = "__YUBALANG_PEAK__"
    for line in reversed(result.stdout.splitlines()):
        if line.startswith(marker):
            return int(line[len(marker):])
    raise RuntimeError("Memory benchmark did not report traced allocations.")


def _measure_execution(source_path: Path, runs: int) -> list[float]:
    def execute() -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            run_file(str(source_path))

    execute()
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        execute()
        samples.append(time.perf_counter() - start)
    return samples


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=_positive_int, default=5)
    parser.add_argument("--iterations", type=_positive_int, default=1000)
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    options = parser.parse_args(arguments)

    function_workload = (
        "func define noop\n"
        "endfunc\n"
        f"loop for {options.iterations}\n"
        "    func call noop\n"
        "endloop\n"
    )
    arithmetic_workload = (
        f"loop for {options.iterations}\n"
        "    arith add 10 5\n"
        "endloop\n"
    )
    collection_workload = (
        "define var values: list = []\n"
        f"loop for {options.iterations}\n"
        "    list append values 1\n"
        "endloop\n"
    )
    with tempfile.TemporaryDirectory(prefix="yubalang-benchmark-") as directory:
        folder = Path(directory)
        workloads = {
            "startup": "",
            "function_calls": function_workload,
            "arithmetic": arithmetic_workload,
            "collections": collection_workload,
        }
        paths = {}
        for name, source in workloads.items():
            path = folder / f"{name}.yl"
            path.write_text(source, encoding="utf-8")
            paths[name] = path
        paths["example_functions"] = ROOT / "examples" / "functions.yl"
        paths["example_collections"] = ROOT / "examples" / "collections.yl"
        samples = {name: _measure(path, options.runs) for name, path in paths.items()}
        execution_samples = {
            name: _measure_execution(path, options.runs)
            for name, path in paths.items()
        }
        peak_memory = {
            name: _measure_peak_traced_bytes(path) for name, path in paths.items()
        }

    results = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "runs": options.runs,
        "iterations": options.iterations,
        "peak_traced_bytes": peak_memory,
        "seconds": {
            name: {
                "median": statistics.median(values),
                "minimum": min(values),
                "maximum": max(values),
                "samples": values,
            }
            for name, values in samples.items()
        },
        "execution_seconds": {
            name: {
                "median": statistics.median(values),
                "minimum": min(values),
                "maximum": max(values),
                "samples": values,
            }
            for name, values in execution_samples.items()
        },
    }
    if options.json:
        print(json.dumps(results, indent=2))
    else:
        print(
            f"YubaLANG benchmark | Python {results['python']} | "
            f"{results['platform']} | {options.runs} runs"
        )
        print(f"Workload size: {options.iterations} iterations")
        for name, result in results["seconds"].items():
            execution = results["execution_seconds"][name]
            print(
                f"{name}: process median {result['median']:.6f}s "
                f"(min {result['minimum']:.6f}s, max {result['maximum']:.6f}s), "
                f"execution median {execution['median']:.6f}s, "
                f"peak traced {peak_memory[name]} bytes"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
