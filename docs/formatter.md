# YubaLANG formatter

The built-in `fmt` command formats `.yl` files with a consistent style:

- Four spaces per nested `if`, `func define`, or `loop` block.
- `else` and `elseif` align with their matching `if`; closing statements align
  with the block's opening statement.
- Existing blank lines and comments are retained, with indentation normalized.
- Statement text, including strings and inline comments, is otherwise
  preserved. Write mode uses UTF-8 and a single final LF newline; check mode
  ignores the difference between LF and CRLF line endings.

Format one file or all `.yl` files under a directory recursively:

```text
py YubaLANG.py fmt --write path\to\program.yl
py YubaLANG.py fmt --write path\to\project
```

`--write` is the default. To check formatting without changing files, use:

```text
py YubaLANG.py fmt --check path\to\project
```

The check exits with status 1 and lists files that need formatting, making it
suitable for CI. For example, add the following step after checking out the
project and setting up Python:

```text
py YubaLANG.py fmt --check .
```

Malformed quoting or unclosed/mismatched blocks are reported instead of being
rewritten. The regression tests parse formatted source and compare execution
output across expressions, functions with named/default/variadic parameters,
records, assertions, and exception blocks. Run the formatter tests with:

```text
py -m unittest tests.test_formatter
```
