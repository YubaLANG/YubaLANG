# YubaLANG standard library

YubaLANG 1.3 provides bundled modules under the reserved `std.*` namespace.
Import one like any other module and call its functions with `func call`:

```hl
import std.path as path
import std.json as json

define var joined: string = ""
define var value: dict = {}
func call path.join "data" "settings.json" -> joined
func call json.loads '{"enabled": true}' -> value
```

These modules are part of the YubaLANG runtime. They do not need a manifest
dependency, package installation, or network access (except `std.http`). The
namespace is reserved: an import matching a bundled `std.*` module resolves to
the standard library before local or package modules.

## Modules

| Module | Functions |
| --- | --- |
| `std.path` | `join`, `normalize`, `basename`, `dirname`, `extension`, `is_absolute`, `resolve`, `relative` |
| `std.fs` | `read_text`, `write_text`, `read_bytes`, `write_bytes`, `exists`, `is_file`, `list_dir`, `mkdir`, `remove_file` |
| `std.time` | `now`, `utc_iso`, `parse_iso`, `sleep` |
| `std.random` | `seed`, `integer`, `uniform`, `choice` |
| `std.math` | `abs`, `ceil`, `floor`, `sqrt`, `pow`, `sin`, `cos`, `is_finite`, `pi`, `e` |
| `std.json` | `loads`, `dumps` |
| `std.encoding` | `utf8_encode`, `utf8_decode`, `base64_encode`, `base64_decode` |
| `std.process` | `args`, `env`, `exit`, `run` |
| `std.http` | `request` |

`func call namespace.function ... -> destination` stores the result in an
existing variable. Use `bytes` for binary values, `dict` for JSON objects and
HTTP responses, and `list` for process arguments and directory entries.

## Paths and files

Paths use the host operating system's `pathlib.Path` semantics. Separators,
absolute-path checks, normalization, and resolution therefore follow the
platform running the program; the library does not reinterpret a Windows path
as a POSIX path or vice versa. `resolve` makes a path absolute and resolves
existing path components. `join` and `normalize` are lexical operations and
do not themselves check file existence.

Text file APIs use strict UTF-8 without adding a byte-order mark; a BOM already
in a file is preserved as the first text character. `read_bytes` and
`write_bytes` handle raw bytes. `write_text` and `write_bytes` create a new
file by default and fail rather than overwriting an existing file. Pass
`overwrite=true` to replace it atomically using a temporary file in the same
directory. Parent directories are not created implicitly. `remove_file`
removes one file or symbolic link and never recursively deletes directories.
The filesystem APIs operate with the program's host privileges; they are not a
sandbox or a path-containment boundary.

```hl
import std.fs as fs

define var contents: string = ""
func call fs.read_text "notes.txt" -> contents
func call fs.write_text "copy.txt" contents
```

## Time, randomness, math, data, and encoding

`std.time.now()` returns a Unix timestamp in seconds. `utc_iso(timestamp)`
formats an RFC 3339-compatible UTC timestamp ending in `Z`; `parse_iso(text)`
returns a Unix timestamp and rejects strings without an explicit UTC offset.
`sleep(seconds)` blocks the current program and rejects negative durations.
Tests can supply a clock to the host `Runtime` constructor instead of relying
on wall-clock time.

`std.random` owns a generator per runtime. `seed(integer)` makes subsequent
results reproducible; `integer(minimum, maximum)` includes both endpoints,
`uniform(minimum, maximum)` returns a float, and `choice(values)` requires a
non-empty list, tuple, or string. Tests can also inject a seeded generator
through the host `Runtime` constructor. This module is not a cryptographic
random source.

`std.math` provides common scalar operations and the `pi()` and `e()` constants
as zero-argument functions. `std.json.loads(text)` parses JSON into YubaLANG
values. `loads` rejects non-standard numeric constants. `dumps(value,
indent=none, sort_keys=false)` emits JSON, preserves Unicode characters, and
rejects non-finite floating-point numbers. Unsupported host values (such as
sets and bytes) produce explicit errors.

`std.encoding.utf8_encode(text)` and `utf8_decode(bytes)` use strict UTF-8.
`base64_encode(bytes)` returns ASCII text, and `base64_decode(text)` validates
the input rather than accepting malformed data.

## Process APIs

`std.process.args()` returns arguments supplied after the source file or
project separator. For projects, pass them after `--`:

```text
YubaLANG run [project-directory] -- first second
YubaLANG main.yl first second
```

`env(name)` returns a string or `none` when the variable is unset. `exit(code)`
terminates the program with an integer status from 0 through 255. `run(args,
timeout=30.0, max_output_bytes=1048576)` starts a subprocess with an explicit
non-empty list of string arguments, no shell, and closed standard input. It
returns a dictionary containing `exit_code`, `stdout`, and `stderr`; output
fields are bytes. The default timeout is 30 seconds, the maximum is one hour,
and combined captured output is limited to 1 MiB by default (1 byte through
64 MiB).
A timeout, output-limit breach, or operating-system launch failure is an
explicit runtime error. The child inherits the current working directory and
environment and runs with the caller's privileges; this is not a sandbox.

## HTTP client

`std.http.request(url, method="GET", body=none, headers=none, timeout=10.0,
max_bytes=1048576)` is synchronous and returns a dictionary with integer
`status`, string `headers`, and byte `body`. HTTP error statuses such as 404
are returned as responses; transport, timeout, and policy errors are reported
as runtime errors.

The client follows at most five redirects (using the standard 301/302/303
POST-to-GET behavior and preserving methods for 307/308), accepts only HTTP(S)
URLs without embedded user information (including redirect targets), and never
downgrades an HTTPS request to HTTP.
TLS certificate and hostname verification use the platform's default verified
TLS configuration and cannot be disabled through this API. Authorization,
cookie, and proxy-authorization headers are stripped on cross-origin
redirects. No cookie jar or credential store is used. The timeout is a
per-socket-operation timeout, must be greater than zero, and is at most 300
seconds; DNS lookup is not covered, and a server that continually sends data
may take longer than that overall. Response bodies are streamed and limited
to 1 MiB by default, with a configurable maximum of 64 MiB. String request
bodies are encoded as UTF-8; byte request bodies remain unchanged. Response
bodies are always returned as bytes.

```hl
import std.http as http

define var response: dict = {}
func call http.request "https://example.invalid/status" -> response
```

Network access is not required for other standard-library modules. Tests for
HTTP behavior should use local fixtures rather than an external service.

## Stability and async policy

The standard-library API baseline is version 1.0, bundled with the YubaLANG
1.3 runtime. The runtime version selects the standard-library API; a project
manifest does not pin standard-library modules separately.

- New modules and functions may be added compatibly within a minor runtime
  release.
- Existing names, argument meanings, return shapes, encoding behavior, and
  documented errors remain stable within a minor release line.
- A breaking change requires a major runtime version and migration guidance.
- A deprecated API must document its replacement and remain available through
  at least one subsequent minor release before removal.
- Patch releases may correct behavior that contradicts this reference but
  must not silently repurpose an API.
- Platform or network APIs must document their side effects, resource limits,
  and error behavior. Standard-library exceptions are source-located.

The 1.3 API is synchronous. YubaLANG has no event loop, cancellation model, or
concurrent task semantics, so asynchronous I/O is deferred; the HTTP client
and sleep operation block the calling program. Time and randomness have
injectable host-runtime seams, filesystem and subprocess tests use isolated
temporary fixtures, and HTTP tests use local servers. No standard-library
operation is a security sandbox.
