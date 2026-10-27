# YubaLANG standard library

## Current APIs and future organization

The current built-ins are documented as language commands and grouped by
purpose in the [built-in reference](builtins.md):

| Area | Current API |
| --- | --- |
| Text and conversion | `text`, `ascii`, `chr`, `format`, `ord`, `repr`, `type`, `convert` |
| Collections and iteration | `list`, `dict`, `set`, `tuple`, `len`, `map`, `filter`, `iter`, `next`, `range`, `slice`, `sorted`, `zip` |
| Arithmetic | `arith` operations and numeric conversions |
| Files | `open`, `file read`, `file write`, `close` |
| Records and values | `record`, `getattr`, `hasattr`, `setattr`, `callable`, `vars` |
| Runtime support | `assert`, `throw`, `try`, `wait`, and `ffi` |

The Python modules under `lang/` are implementation details unless they are
explicitly documented as a YubaLANG command or public Python API. Users should
depend on the language-level forms and their documented behavior, not on
internal module names.

The organization for additional standard-library APIs is not yet decided.
Whether to add importable `std.*` modules is deferred until the language's
package and import model is settled; the current command-oriented built-ins do
not imply a decision for future APIs.

## API stability

The following policy applies to documented standard-library commands:

- Additive APIs may be introduced in a minor language release.
- Existing command forms, destination types, and documented errors remain
  compatible within a minor release line.
- A breaking change requires a major language version and migration guidance.
- A deprecation must be documented with a replacement and remain supported
  through at least one subsequent minor release before removal.
- Patch releases may correct behavior that contradicts the reference, but
  must not silently repurpose a documented command or argument.
- Experimental APIs must be labeled as experimental in both the reference
  and their command documentation.

Standard-library behavior must be testable without network access. APIs that
depend on time, randomness, environment state, or external processes should
provide deterministic tests through injected values or isolated test fixtures.

## Current platform and I/O guarantees

File commands use the host filesystem. Text files use UTF-8, paths follow the
host platform's path rules, and file operations report operating-system errors
as source-located diagnostics. Binary modes operate on `bytes` and
`bytearray`. Imported YubaLANG modules and native libraries run with the
program's privileges; they are not sandboxed.

Importable standard-library modules, a cross-platform path module, date/time,
random, structured-data, process, and HTTP APIs are not implemented in the
current 1.3 codebase. Their organization and import behavior remain open
roadmap work; do not treat them as shipped APIs. Introduce them only with their
module names, error behavior, portability guarantees, and deterministic test
seams documented.
