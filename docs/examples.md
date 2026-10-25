# Runnable examples

Each output-based example is checked against its paired `.expected.txt` file
by the test suite. Run one with `YubaLANG test examples\<name>.yl` on Windows,
or `YubaLANG test examples/<name>.yl` on macOS/Linux. The runner executes a
program with its own directory as the working directory, so relative file
paths in an example resolve from that directory.

| Program | Demonstrates |
| --- | --- |
| [Getting started](../examples/getting-started.yl) | Variables, comparisons, conditionals, and functions. |
| [Functions](../examples/functions.yl) | Function parameters, return values, and `filter`. |
| [Collections](../examples/collections.yl) | Sorting, slicing, and aggregation. |
| [Strings and iteration](../examples/strings_and_iteration.yl) | Unicode character helpers and `enumerate`. |
| [File I/O](../examples/file_io.yl) | Opening, reading, and closing a text file. |
| [Error handling](../examples/error_handling.yl) | `throw`, `catch`, and `finally`. |
| [Modules](../examples/modules/main.yl) | Importing and calling a namespaced local module. |
| [Testing](../examples/testing/smoke.yl) | A minimal output fixture for `YubaLANG test`. |
| [C ABI](../examples/ffi_add.yl) | Calling a native C function. See the [C ABI guide](c-abi.md) to build the library for your platform. |

Run the testing example with `YubaLANG test examples/testing`. The
[multi-module project tutorial](project-tutorial.md) adds a local package
dependency and runs an output test. Native interop needs a C compiler and
platform-specific library names, as described in the C ABI guide.
