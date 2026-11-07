# YubaLANG documentation

Use this page to find a guide by task. The [master reference](master-reference.md)
is the consolidated reference for the current language, runtime, and tools.
The [1.3 language reference](1.3-docs.md) describes the versioned language
specification; consult it alongside the [migration notes](1.3-migration.md)
when updating code from 1.2.

## Start learning

1. [Install or update YubaLANG](install.md).
2. Follow [Getting started](getting-started.md) and run the example.
3. Try the interactive interpreter with `YubaLANG repl`.
4. Choose a program from the [runnable example catalog](examples.md).

## Learn and look things up

- [Master reference](master-reference.md): language, runtime, commands, and
  developer tools.
- [1.3 language reference](1.3-docs.md): versioned grammar, expressions,
  types, control flow, and runtime semantics.
- [Built-ins](builtins.md): function signatures and examples.
- [Standard library](standard-library.md): bundled `std.*` modules, API
  behavior, limits, and stability policy.
- [Examples](examples.md): runnable programs and what each demonstrates.

## Build and maintain projects

- [Projects and packages](package-manager.md): manifests, imports, lockfiles,
  and YubaLANG/YubaPKG compatibility.
- [Multi-module tutorial](project-tutorial.md): a worked local-package project.
- [Formatter](formatter.md): check and format `.yl` files.
- [Language server](language-server.md): editor integration and supported LSP
  features.
- [Installation and releases](install.md): platform targets and install/update
  instructions.
- [Runtime performance](performance.md): benchmarks and measurement details.

## Interoperability and version history

- [Calling native C functions](c-abi.md).
- [1.2 to 1.3 migration notes](1.3-migration.md).
- [1.3.0 release notes](1.3-release-notes.md).

Standalone release executables are available for Windows x64, Linux x64,
macOS Intel, and macOS Apple Silicon, and bundle Python. Running from source
requires Python 3.10 or newer; Git is needed only for Git dependencies.
See [installation](install.md) for platform targets and build details.
