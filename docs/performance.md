# Runtime performance

Run repeatable startup, function-call, arithmetic, and collection baselines
from the repository root:

```powershell
py -3 tools\benchmark.py
```

Each case gets one warm-up run followed by five measured runs. Results include
process-level wall time (including Python startup), in-process interpreter
execution time, and peak Python-traced allocations from a separate run. Traced
memory is not process RSS and excludes allocations made by native libraries.
Adjust the sample count and workload size as needed:

```powershell
py -3 tools\benchmark.py --runs 10 --iterations 5000
py -3 tools\benchmark.py --runs 5 --iterations 1000 --json
```

Results include the Python version and platform because interpreter startup
and execution costs vary across environments. Compare runs made with the same
Python build, platform, and options. These measurements are baselines, not
performance guarantees, and the function-call workload does not represent
every YubaLANG program.

In one local microbenchmark of 10,000 repeated no-op function calls, cached
tokenization took about 14 ms versus about 70 ms without the cache. This
measures a narrow, repeated-source workload; use the harness on representative
programs before drawing broader conclusions.
