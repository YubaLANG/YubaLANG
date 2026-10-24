# YubaLANG Built-in Functions

Built-ins use command syntax. Unless stated otherwise, the destination variable
must already exist and have the matching YubaLANG type.

## Character and string functions

```hl
ascii <value_or_variable> <string_destination>
chr <integer_or_variable> <string_destination>
ord <character_or_variable> <integer_destination>
format <value_or_variable> <format_spec> <string_destination>
repr <value_or_variable> <string_destination>
```

`format` also accepts `format <value_or_variable> <string_destination>` to use
the default format specification. For example:

```hl
define var code: int = 9731
define var symbol: string = ""
chr code symbol
text output symbol
```

## Iteration and collections

These functions return a list, except `slice`, which preserves the source
sequence type. Their destination variables should be declared as `list` (or as
the source type for `slice`).

```hl
enumerate <iterable> <list_destination> [start]
filter <function> <iterable> <list_destination>
iter <iterable> <iterator_destination>
map <function> <iterable> <list_destination>
next <iterator> <destination> [default]
range <stop> <list_destination>
range <start> <stop> <list_destination> [step]
reversed <iterable> <list_destination>
slice <sequence> <start> <stop> <destination> [step]
sorted <iterable> <list_destination> [reverse]
zip <iterable1> <iterable2> [...] <list_destination>
```

`iter` creates its destination variable if it does not already exist. `next`
raises an error when the iterator is exhausted and no default is supplied.
`enumerate` produces `(index, value)` tuples; `zip` produces tuples. `sorted`
accepts `true` or `false` for its optional `reverse` argument.

`map` and `filter` accept a built-in unary function name (such as `abs`, `int`,
`float`, `str`, `bool`, `ascii`, `repr`, or `len`) or a user-defined function
that takes one parameter and returns a value. Functions can be declared with
parameters, defaults, named arguments, and return values:

```hl
func define is_positive value
    define var result: bool = false
    compare value > 0 result
    return result
endfunc

define var numbers: list = [-2, 0, 5]
define var positives: list = []
filter is_positive numbers positives
```

An explicit function result can be assigned with
`func call <name> [arguments] -> <destination>`.
Defaults are evaluated at definition time. Required parameters must precede
defaulted parameters; positional call arguments must precede `name=value`
arguments. A final `*name` parameter collects extra positional arguments into
a tuple.

## Existing built-ins

The interpreter also supports `all`, `any`, `bool`, `callable`, `id`, `len`,
`type`, `vars`, `bin`, `divmod`, `hex`, `oct`, `pow`, `convert`, `bytes`,
`bytearray`, `getattr`, `hasattr`, `setattr`, and `open`. Arithmetic commands
use `arith <operation> <value>` or `arith <operation> <value1> <value2>`.
Use `close <file_variable>` to close a file before the program ends; open files
are also closed automatically when a file run finishes.

Commands that write to a destination variable check the result against that
variable's declared type. An integer result may be widened to a `float`
destination; other incompatible assignments report a type error instead of
leaving the variable's declared type inconsistent with its value. Use
`convert` when intentionally changing a variable's type.

Collections have no YubaLANG-specific size cap; their practical limits depend
on available host memory. If allocation raises `MemoryError`, execution
reports it as a source-located runtime diagnostic rather than exposing a
Python traceback.

## Type annotations

The built-in scalar types include `none`. Use `T?` as shorthand for a union
with `none`, and `A | B` for other unions. Generic collection annotations
check their contents recursively: `list[T]`, `set[T]`, `dict[K, V]`,
`tuple[T]` (homogeneous), and `tuple[A, B]` (fixed length and per-position
types). Mutations are checked too, including changes through aliases of a
typed collection. Generic element types are invariant; an `int` element is not
silently widened inside `list[float]`.

Functions can declare parameter and return types. Function references may be
stored in variables with a function type and passed as callbacks:

```hl
func define increment value:int -> int
    return value
endfunc

define var transform: (int)->int = increment
define var values: list[int] = [1, 2]
define var results: list[int] = []
map transform values results
```

Every parameter and the return type must be annotated, and the function must
not be variadic, to match a function type. These annotations are enforced at
calls and returns.

Run `py -3 YubaLANG.py check <file.yl>` to report syntax problems and
statically-detectable type mismatches without executing the file. This check
is opt-in. It infers types from literals, declarations, and supported command
results, including typed function references and generic literals. Unknown or
dynamic values are left unchecked; runtime checks remain authoritative.

## Assertions and runtime limits

`assert <boolean> [message]` stops execution with a source-located error if
the boolean is false. The optional message must be a string literal or string
variable. Assertions can express function preconditions and postconditions
using `compare` to produce the boolean:

```hl
func define require_positive value
    define var valid: bool = false
    compare value > 0 valid
    assert valid "value must be positive"
    return value
endfunc

define var result: int = 0
func call require_positive 5 -> result
```

Use `throw <value>` with `try`, optional `catch [name]`, and optional
`finally` / `endtry` blocks for structured error handling. A named catch
variable contains the thrown value or, for a runtime error, its message string.
`finally` runs even when a function returns from inside the protected block.
Uncaught errors retain their source location and function call frames.

User-defined functions may be nested up to 128 calls deep. Exceeding this
limit reports a source-located recursion error instead of exposing an
interpreter traceback.

## Records

Use `record define <Name> <field>:<type>...` to declare a record and
`record create <Name> <variable> <value>...` to construct it. Field values
follow declaration order. `getattr`, `hasattr`, and `setattr` access record
fields; construction and mutation enforce field types. Records compare by type
and field values. Assigning a record to another variable shares the same
mutable value rather than making a copy.
