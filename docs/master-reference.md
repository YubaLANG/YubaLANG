# YubaLANG Master Reference

This is the central reference for the language and its tools. It documents
the implemented behavior in this repository, including the extended type
annotations, runtime, modules, package workflow, formatter, test runner,
language server, and native C interface. The focused guides linked below
provide additional installation and operational detail.

## Contents

- [Running YubaLANG](#running-yubalang)
- [Source syntax](#source-syntax)
- [Lexical rules and evaluation](#lexical-rules-and-evaluation)
- [Expressions and assignment](#expressions-and-assignment)
- [Variables and types](#variables-and-types)
- [Expressions and literals](#expressions-and-literals)
- [Commands and built-ins](#commands-and-built-ins)
- [Control flow](#control-flow)
- [Functions](#functions)
- [Records](#records)
- [Errors, assertions, and cleanup](#errors-assertions-and-cleanup)
- [Modules and packages](#modules-and-packages)
- [Developer tools](#developer-tools)
- [Language server](#language-server)
- [Native C interface](#native-c-interface)
- [Runtime behavior and limitations](#runtime-behavior-and-limitations)

## Running YubaLANG

Run a source file directly:

```text
YubaLANG.exe path\to\program.yl
```

When running from a source checkout, use `py -3 YubaLANG.py` instead of
`YubaLANG.exe`.

| Command | Purpose |
| --- | --- |
| `YubaLANG <file.yl>` | Execute a YubaLANG source file. |
| `YubaLANG run [project-directory]` | Execute the manifest entry point. |
| `YubaLANG repl` | Start an interactive interpreter session. |
| `YubaLANG check <file.yl>` | Report static diagnostics without execution. |
| `YubaLANG fmt [--check\|--write] <file-or-directory>...` | Check or format source. |
| `YubaLANG test [options] [file-or-directory]` | Run output-based tests. |
| `YubaLANG package <subcommand>` | Manage project dependencies. |
| `YubaLANG --lsp` | Start the stdio language server. |

The [installation guide](install.md) documents supported release platforms,
installers, and executable distribution.
New users can start with the [getting-started guide](getting-started.md).

## Source syntax

YubaLANG source files use the `.yl` extension. Each command is written on its
own line. Indentation is for readability and formatted block structure;
commands are grouped by explicit opening and closing keywords.

Comments begin with `#`, either on their own line or after a command.

```hl
# Full-line comment
text output "Hello!" # Inline comment
```

Strings may use single or double quotes. Common escapes include `\n`, `\t`,
`\\`, `\"`, and `\'`. Quote Windows path backslashes as `\\`.

## Lexical rules and evaluation

Each nonblank source line contains one command. There is no line-continuation
syntax; indentation is not significant to execution, and block structure is
defined by opening and closing commands. A `#` outside a quoted string starts
a comment that continues to the end of the line.

Variable names must be valid identifiers according to Python's Unicode
identifier rules (`str.isidentifier()`); for example, `count`, `_index`, and
`café` are valid, while `2count` and `count-value` are not. Identifier
keywords are not reserved solely by their spelling.

Values are literals or variable references. Supported literal forms include
numbers, quoted strings, booleans, `none`, and list, dictionary, set, and tuple
literals. A literal may contain variable references. Unary `+` and `-` apply
to numeric values; arithmetic commands such as `arith add` produce output
rather than an expression value. YubaLANG has no general operator expressions
or line continuation.

## Variables and types

Declare a variable with `define var <name>: <type> = <value>`:

```hl
define var count: int = 3
define var ratio: float = 0.75
define var greeting: string = "Hello"
define var enabled: bool = true
define var maybe_count: int? = none
define var values: list[int] = [1, 2, 3]
define var names: set[string] = {"Ada", "Grace"}
define var lookup: dict[string, int] = {"Ada": 1}
define var point: tuple[int, int] = (4, 9)
define var payload: bytes = "hello"
define var buffer: bytearray = "hello"
```

### Built-in types

| Type | Description |
| --- | --- |
| `int` | Integer; booleans are not integers for type checking. |
| `float` | Floating-point number. An integer may widen to float where scalar assignment allows it. |
| `string` | Unicode text. |
| `bool` | `true` or `false`. |
| `none` | The single `none` value; useful in optional types. |
| `list`, `dict`, `set`, `tuple` | Mutable list, mutable mapping, mutable set, and immutable tuple. |
| `bytes`, `bytearray` | Immutable bytes and mutable byte sequence. |
| `file` | Open file handle created by `open`. |
| `iterator` | Iterator created by `iter`. |

### Union, optional, and generic types

`A | B` accepts a value matching either type. `T?` is shorthand for
`T | none`. Unions can be nested in collections.

```hl
define var result: int | string = "pending"
define var selected: int? = none
define var scores: list[int | float] = [10, 2.5]
define var attributes: dict[string, string?] = {"nickname": none}
define var pair: tuple[int, string] = (7, "seven")
```

`list[T]`, `set[T]`, `dict[K, V]`, and `tuple[T]` (homogeneous) validate their
contents. `tuple[A, B, ...]` specifies a fixed-length tuple with a type for
each position. Generic collection element types are invariant: integer values
are not widened inside `list[float]`.

Typed mutable collections are checked at creation, assignment, and supported
mutations. Mutations through aliases are checked too. The unparameterized
forms, such as `list`, retain their existing behavior without element checks.

Function types use `(A, B) -> R`; `() -> R` describes a zero-argument
function. A function assigned to this type must annotate every parameter and
its return type and must not be variadic. Keep parameter annotations compact,
such as `value:int|string`, so their boundaries remain unambiguous.

```hl
func define identity value:int -> int
    return value
endfunc

define var transform: (int)->int = identity
```

### Runtime checks and static checks

Assignments to declared variables and record fields are runtime checked.
Integer-to-float widening is supported for scalar values, not collection
elements. `convert <variable> to <type>` intentionally changes a variable's
declared type and value.

`YubaLANG check <file.yl>` runs an opt-in static analysis without executing the
program. It diagnoses statically evident syntax and type mismatches, including
known literal, generic, and typed-function cases. Dynamic or unknown values
may not be diagnosed; runtime checks remain authoritative.

## Expressions and literals

Expression-bearing commands accept literals, variable names, collections,
parentheses, arithmetic operators, comparisons, and boolean operators. The
precedence and grammar are specified in the
[YubaLANG 1.3 reference](1.3-docs.md#formal-grammar).

`set <variable> = <expression>` assigns to an existing variable without
changing its declared type:

```hl
define var base: int = 3
define var result: int = 0
set result = (base + 2) ** 2
text output result
```

The expression subset is available in initializers, assignments, returns,
output, comparisons, conditions, and loop counts/conditions. Other command
arguments retain their documented forms. Values can be literals or variable
names. Collection literals can refer to existing variables:

```hl
define var first: int = 10
define var values: list = [first, 20, "thirty"]
```

Strings are quoted. `if`, `elseif`, and `loop while` require boolean
conditions. `compare <expression> <bool-destination>` stores a comparison
result; the legacy four-operand comparison form is also supported.

## Commands and built-ins

Unless noted, a command that writes a result requires an existing destination
variable of a compatible declared type. `iter` creates its iterator
destination if it does not already exist.

### Output, input, conversion, and comparison

```text
text output <value-or-variable>
text input <string-variable>
convert <variable> to <type>
compare <value1> <operator> <value2> <bool-variable>
```

`text output` prints a value followed by a newline. `text input` reads one
line into an existing string variable. `convert` also accepts the legacy
two-argument form `convert <variable> <type>`.

### Arithmetic

Arithmetic commands print their result:

```text
arith add|sub|mul|div|mod|pow|divmod <value1> <value2>
arith abs|round|bin|hex|oct|sum|max|min <value>
arith max|min <value1> <value2>
```

`sum`, `max`, and `min` accept a list, tuple, or set; `max` and `min` also
accept two operands. Division and modulo by zero are runtime errors.

### Collections and iteration

| Command form | Behavior |
| --- | --- |
| `list append <list> <value>` | Append a value. |
| `list get <list> <index> <destination>` | Read a zero-based list index. |
| `list len <list> <int-destination>` | Store list length. |
| `dict set <dict> <key> <value>` | Insert or replace a mapping entry. |
| `dict get <dict> <key> <destination>` | Read an existing mapping entry. |
| `set add <set> <value>` | Add a member. |
| `set remove <set> <value>` | Remove an existing member. |
| `tuple get <tuple> <index> <destination>` | Read a zero-based tuple index. |
| `all <iterable> <bool-destination>` | Test whether all values are truthy. |
| `any <iterable> <bool-destination>` | Test whether any value is truthy. |
| `len <value> <int-destination>` | Store string or collection length. |
| `enumerate <iterable> <list-destination> [start]` | Produce `(index, value)` pairs. |
| `filter <function> <iterable> <list-destination>` | Keep values whose callback result is truthy. |
| `iter <iterable> <iterator-destination>` | Create an iterator. |
| `map <function> <iterable> <list-destination>` | Apply a unary callback to each value. |
| `next <iterator> <destination> [default]` | Read the next value or supplied default. |
| `range <stop> <list-destination>` | Produce integers from zero to `stop` (exclusive). |
| `range <start> <stop> <list-destination> [step]` | Produce an integer range. |
| `reversed <iterable> <list-destination>` | Return values in reverse order. |
| `slice <sequence> <start> <stop> <destination> [step]` | Slice a supported sequence. |
| `sorted <iterable> <list-destination> [reverse]` | Return sorted values; `reverse` is boolean. |
| `zip <iterable1> <iterable2> [...] <list-destination>` | Pair values into tuples, stopping at the shortest input. |

`slice` supports strings, lists, tuples, bytes, and bytearrays. `iter` and
`next` use Python-style iterator behavior; reading an exhausted iterator
without a default raises a language error.

### Strings, conversion helpers, and attributes

| Command form | Behavior |
| --- | --- |
| `ascii <value> <string-destination>` | Store an ASCII-escaped representation. |
| `chr <integer> <string-destination>` | Convert a Unicode code point to a character. |
| `ord <character> <int-destination>` | Convert one character to its code point. |
| `format <value> <spec> <string-destination>` | Format a value with a format specification. |
| `format <value> <string-destination>` | Format with the default specification. |
| `repr <value> <string-destination>` | Store the representation of a value. |
| `bool <value> <bool-destination>` | Convert a value to boolean truthiness. |
| `bytes <value> <bytes-destination>` | Create bytes from a value. |
| `bytearray <value> <destination>` | Create a mutable byte sequence. |
| `getattr <object> <attribute-or-key> <destination>` | Read a record field, dictionary key, or supported attribute. |
| `hasattr <object> <attribute-or-key> <bool-destination>` | Test for a record field, dictionary key, or attribute. |
| `setattr <object> <attribute-or-key> <value>` | Update a record field, dictionary key, or supported attribute. |

Record field access is type checked. Dictionary `getattr`/`setattr` use the
given key; record attribute names may be unquoted.

### Other built-ins

- `callable <function-name> <bool-destination>` checks for a supported
  built-in or user-defined function.
- `id <variable> <int-destination>` reports the host identity of the value.
- `type <variable> <string-destination>` stores its declared YubaLANG type.
- `vars` prints active variables and defined functions.
- `wait <seconds>` pauses for the specified duration.
- `open <path> <mode> <file-destination>` opens a file. Text files use UTF-8;
  modes containing `b` open binary files.
- `file read <file-variable> <destination>` reads the rest of an open file.
  Text mode requires a `string` destination; binary mode requires `bytes` or
  `bytearray`.
- `file write <file-variable> <value>` writes a string to a text file or
  bytes/bytearray to a binary file.
- `close <file-variable>` closes an open file.

Built-in unary functions accepted by `map` and `filter` include `abs`, `bool`,
`chr`, `int`, `float`, `str`, `ord`, `round`, `ascii`, `repr`, and `len`.
User-defined functions must return a value when used as a `map` callback.

See the [built-in reference](builtins.md) for additional examples and
type-specific details.

## Control flow

### Conditions

```hl
if <boolean-literal-or-variable>
    ...
elseif <boolean-literal-or-variable>
    ...
else
    ...
endif
```

`elseif` and `else` are optional; an `if` may contain multiple `elseif`
branches and at most one `else`.

### Loops

```hl
loop for <integer-count-or-variable>
    ...
endloop

loop while <boolean-literal-or-variable>
    ...
endloop
```

`break` exits the innermost loop. `continue` starts its next iteration.
`return` exits the current function.

## Functions

Define and call functions with `func define` and `func call`:

```hl
func define greet name greeting="Hello"
    text output greeting
    text output name
endfunc

func call greet "Ada"
func call greet name="Grace" greeting="Welcome"
```

Parameters are positional by default. Required parameters precede parameters
with defaults; defaults are evaluated when the function is defined. Calls may
use positional arguments followed by `name=value` arguments. Missing,
duplicate, unknown, or excessive arguments are errors. A final `*name`
parameter collects remaining positional arguments into a tuple.

Function calls have local scopes. A function may `return` without a value or
return a value; assign a returned value with `->`:

```hl
func define identity value
    return value
endfunc

define var answer: int = 0
func call identity 42 -> answer
```

### Typed signatures and function references

Annotate parameters as `name:type` and the return type after `->`:

```hl
func define is_positive value:int -> bool
    define var positive: bool = false
    compare value > 0 positive
    return positive
endfunc

define var predicate: (int)->bool = is_positive
```

YubaLANG does not currently have general arithmetic expressions: arithmetic
commands print their results. Typed function annotations enforce parameter
and return values; typed function references can be used by `map` and
`filter`.

## Records

Define a named record type, then construct a value in field declaration order:

```hl
record define Point x:int y:int
record create Point origin 10 20

define var x: int = 0
getattr origin x x
setattr origin y 25
```

`getattr`, `hasattr`, and `setattr` work with records. Construction and
mutation check declared field types. Same-type records compare structurally.
Assigning a record aliases the same mutable value. Records currently have no
methods, inheritance, or default fields.

## Errors, assertions, and cleanup

Invalid syntax, unknown commands/types, undefined names, conversion failures,
type errors, index/key errors, I/O errors, and arithmetic errors are reported
with source location and a source-line caret. Likely misspellings may receive
a suggestion. Errors raised inside functions retain their original location
and include call frames; ordinary language diagnostics do not expose Python
tracebacks.

`assert <boolean> [message]` raises a source-located assertion error when the
condition is false. It can express preconditions and postconditions. The
optional message must resolve to a string.

Use `throw <value>` inside `try` blocks:

```hl
try
    throw "configuration is missing"
catch problem
    text output problem
finally
    text output "finished"
endtry
```

`catch` and `finally` are optional. A named catch variable receives the thrown
value, or the runtime error message as a string. `finally` runs when control
leaves the protected block, including when a function returns. Catch blocks
handle language/runtime errors, not Python implementation defects.

Files opened with `open` are tracked by the runtime and closed at the end of
file execution, including those opened in function-local scopes. Use `close`
for deterministic early closure. Runtime-backed iterators and native handles
do not currently have a general cleanup protocol.

User-defined function calls are limited to 128 nested calls. Host memory
exhaustion is reported as a source diagnostic with a sizing hint; collections
have no separate language-defined size cap.

## Modules and packages

Local modules are resolved relative to the importing source file as
`<name>.yl` or `<name>/main.yl`. Dotted imports follow directories. A declared
package dependency resolves to that package's manifest entry. Modules execute
once per runtime; import cycles are errors. Imported functions are called
through their module namespace, and module variables share the runtime's
global scope.

Projects use `yuba.json` and `yuba.lock.json`. Dependencies may refer to local
paths or Git sources with an optional revision. Lockfile format 2 records
resolved Git commits and each package's nested dependency graph. Imports resolve
dependencies from the nearest package manifest; declared dependencies take
precedence over local modules with the same name. Runtime imports validate the
locked graph without network access. Commands include:

```text
YubaLANG package init [directory]
YubaLANG package add <name> --path <path>
YubaLANG package add <name> --git <url> [--rev <revision>]
YubaLANG package install
YubaLANG package update [name]
YubaLANG package list
YubaLANG package check
YubaLANG package remove <name>
```

`YubaLANG run [project-directory]` runs the manifest entry point and checks
installed dependencies when the project declares them. The package tools
support recursive path and Git dependencies, but not a public registry or
semantic-version range solver. Imported modules execute with the program's
privileges; dependencies are not sandboxed. See the
[package guide](package-manager.md).

## Developer tools

### REPL

Start with `YubaLANG repl`. The REPL maintains variables and functions across
commands, collects multiline `if`, `func`, `loop`, and `try` blocks, and
accepts `exit` or `quit` to leave. Enter `reset` to close tracked files and
start with a fresh runtime. End-of-file discards an incomplete block with a
notice.

### Test runner

Tests are `.yl` files paired with sibling `.expected.txt` files. Their exact
standard output is compared in separate interpreter processes. The runner
supports:

```text
YubaLANG test [--filter PATTERN|-k PATTERN] [--json] [file-or-directory]
```

The default directory is `tests/cases`. Text output includes unified diffs
for mismatches. JSON output reports the path, filter, counts, test names,
statuses, details, expected output, and actual output. The runner does not
report coverage: it has no source-level execution counters.

### Formatter

`YubaLANG fmt --write <file-or-directory>` formats `.yl` files; `--check`
reports files that would change without modifying them. It normalizes block
indentation to four spaces, preserves statement text and comments, and
requires valid quoting and matched block structure. See the
[formatter guide](formatter.md).

### Benchmarks

`py -3 tools\benchmark.py` measures process startup, interpreter time, traced
Python allocations, synthetic function/arithmetic/collection workloads, and
runnable example workloads. `--runs` and `--iterations` adjust samples and
workload size; `--json` selects machine-readable output. Traced allocations
are not process RSS. See [runtime performance](performance.md).

## Language server

Start with `YubaLANG --lsp` (or `py -3 YubaLANG.py --lsp` in a checkout). The
stdio LSP provides diagnostics, go-to-definition, hover, completion, signature
help, references, rename, document/workspace symbols, and typo quick fixes.
It supports full and ranged document changes, rejects stale versions, and
clears state on close. The server does not execute source. Symbol search,
references, and rename are limited to documents open in the server; it does
not index unopened files or resolve project dependencies. VS Code requires a
generic LSP client extension. See [language server setup](language-server.md).

## Native C interface

YubaLANG can call a local C library using:

```text
ffi call <library-path> <symbol> <return-type> [<argument-type> <value> ...] [-> <destination>]
```

Supported value types are `i32`, `i64`, `f64`, and `bool`; return types also
include `void`. Arguments are passed by value using the host C calling
convention. Pointers, strings, structures, callbacks, and ownership transfer
are unsupported. Native code can crash or corrupt the process; call only
trusted libraries. See the [C ABI guide](c-abi.md).

## Runtime behavior and limitations

- Modules, path dependencies, and native libraries are not a security
  sandbox; they may perform operations with the process's privileges.
- Mutable lists, dictionaries, sets, bytearrays, and records are shared by
  reference when aliased. Typed generic collection mutations are checked
  against annotations reachable through those aliases.
- There is no general expression language, static inference is conservative,
  and dynamic values may evade static diagnostics while remaining subject to
  runtime checks.
- There is no bytecode compiler, project build command, debugger, coverage
  instrumentation, or filesystem-wide LSP index.
- The runtime has no general deterministic resource protocol for iterators or
  future native resource wrappers. Files are explicitly tracked and closed.
- The C bridge is intentionally narrow and does not transfer pointers or
  ownership.

For an introductory path, begin with the [getting-started guide](getting-started.md)
and [documentation guide](index.md), then
refer to [built-ins](builtins.md), [projects](package-manager.md),
[formatting](formatter.md), [installation](install.md), and
[examples](examples.md).
