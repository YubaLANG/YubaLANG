# Runtime performance

Run repeatable startup, function-call, arithmetic, collection, and runnable
example baselines from the repository root:

```powershell
py -3 tools\benchmark.py
```

By default each case gets one warm-up run followed by five measured runs.
Results include process-level wall time (including Python startup), in-process
interpreter execution time, and peak Python-traced allocations from a separate
run. Traced memory is not process RSS and excludes allocations made by native
libraries. Adjust the sample count and workload size as needed:

```powershell
py -3 tools\benchmark.py --runs 10 --iterations 5000
py -3 tools\benchmark.py --runs 5 --iterations 1000 --json
```

Results include the Python version and platform because interpreter startup
and execution costs vary across environments. Compare runs made with the same
Python build, platform, and options. These measurements are baselines, not
performance guarantees, and the function-call workload does not represent
every YubaLANG program.

A small 3-run sample on Windows 11 with Python 3.14.0 and 500 workload
iterations produced these medians:

| Workload | Process time | Interpreter time | Peak traced allocations |
| --- | ---: | ---: | ---: |
| Startup | 0.1484 s | 0.0008 s | 4,018,131 bytes |
| Function calls | 0.1495 s | 0.0017 s | 4,018,366 bytes |
| Arithmetic | 0.1888 s | 0.0016 s | 4,018,259 bytes |
| Collections | 0.1531 s | 0.0052 s | 4,769,377 bytes |
| Example functions | 0.1555 s | 0.0006 s | 4,018,687 bytes |
| Example collections | 0.1496 s | 0.0005 s | 4,018,884 bytes |

This sample is a smoke baseline from one machine, not evidence that a
different dispatch strategy or bytecode would improve representative
programs. No fixed collection-size limit is imposed; memory-exhaustion
diagnostics are tested separately.

In one local microbenchmark of 10,000 repeated no-op function calls, cached
tokenization took about 14 ms versus about 70 ms without the cache. This
measures a narrow, repeated-source workload; use the harness on representative
programs before drawing broader conclusions.
