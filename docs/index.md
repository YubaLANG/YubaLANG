# YubaLANG documentation

Use this page to find a guide by task. The [master reference](master-reference.md)
is the consolidated reference for the current language, runtime, and tools.
The [1.3 language reference](1.3-docs.md) describes the versioned language
specification; consult it alongside the
[migration notes](releases/1.3-migration.md) when updating code from 1.2.

Supporting documents are grouped into `guides/`, `features/`, `projects/`,
`tools/`, `setup/`, and `releases/`. The versioned language reference and
master reference remain at the top level.

## Start learning

1. [Install or update YubaLANG](setup/install.md).
2. Follow [Getting started](guides/getting-started.md) and run the example.
3. Try the interactive interpreter with `YubaLANG repl`.
4. Choose a program from the [runnable example catalog](guides/examples.md).

## Learn and look things up

- [Master reference](master-reference.md): language, runtime, commands, and
  developer tools.
- [1.3 language reference](1.3-docs.md): versioned grammar, expressions,
  types, control flow, and runtime semantics.
- [Built-ins](features/builtins.md): function signatures and examples.
- [Standard library](features/standard-library.md): bundled `std.*` modules,
  API behavior, limits, and stability policy.
- [Examples](guides/examples.md): runnable programs and what each demonstrates.

## Build and maintain projects

- [Projects and packages](projects/package-manager.md): manifests, imports,
  lockfiles, and YubaLANG/YubaPKG compatibility.
- [Multi-module tutorial](projects/project-tutorial.md): a worked
  local-package project.
- [Formatter](tools/formatter.md): check and format `.yl` files.
- [Language server](tools/language-server.md): editor integration and
  supported LSP features.
- [Installation and releases](setup/install.md): platform targets and install/update
  instructions.
- [Runtime performance](tools/performance.md): benchmarks and measurement details.

## Interoperability and version history

- [Calling native C functions](features/c-abi.md).
- [1.2 to 1.3 migration notes](releases/1.3-migration.md).
- [1.3.0 release notes](releases/1.3-release-notes.md).

## Roadmap

- [YubaLANG 1.4 roadmap](roadmap/1.4.md): proposed release work and major
  feature candidates.
- [YubaLANG feature backlog](roadmap/features.md): long-term language,
  runtime, tooling, and ecosystem candidates.

Standalone release executables are available for Windows x64, Linux x64,
macOS Intel, and macOS Apple Silicon, and bundle Python. Running from source
requires Python 3.10 or newer; Git is needed only for Git dependencies.
See [installation](setup/install.md) for platform targets and build details.
