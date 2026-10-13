# YubaLANG TODO — 1.2 Release

## Release focus

Make YubaLANG easier to install, learn, share, and validate while keeping the
toolchain lightweight. Prefer small, interoperable features over infrastructure
that would be expensive to maintain before the user base grows.

## Prioritization

| Priority | Feature | Scope | Early-user value |
| --- | --- | --- | --- |
| P0 | Contextual interpreter/runtime errors | Low | Very high |
| P0 | Official `fmt` formatter | Low–medium | High |
| P0 | Package manifest and Git/path dependency resolver | Medium | Critical |
| P1 | Basic language server (LSP) | Medium | High |
| P1 | Built-in test runner | Low–medium | High |
| P2 | Cross-platform toolchain installers | Medium–high | High |
| P2 | Minimal C ABI / system bindings | Medium | High |

Priorities are a suggested implementation order, not a commitment to ship an
item before its dependencies are understood.

## 1. Zero-to-hero onboarding and ergonomics

### Cross-platform toolchain installers

- [ ] Define and document a clean installation layout, PATH setup, and
  uninstall/update behavior.
- [ ] Add a Linux installer for the compiler and runtime.
- [ ] Add a macOS installer for Intel (x86_64) and Apple Silicon (ARM64).
- [ ] Add a Windows PowerShell installer.
- [ ] Document and test supported operating systems, architectures,
  prerequisites, checksums/signatures, and upgrade behavior.
- [ ] Provide copyable first-run instructions and verify the installed toolchain
  can run a sample project.

### Basic language server

- [x] Implement a lightweight LSP with document open/change/close support.
- [x] Report syntax diagnostics with source ranges.
- [x] Support jump-to-definition for variables and functions.
- [x] Provide hover documentation for language syntax and built-ins.
- [x] Document editor setup and test the server with a small example project.

### Official formatter

- [ ] Specify a consistent formatting style for YubaLANG source files.
- [ ] Implement a formatter with a check mode and a write mode.
- [ ] Keep formatting stable and avoid changing program semantics.
- [ ] Add formatter fixtures covering comments, strings, collections,
  indentation, and nested control flow.
- [ ] Document how to format a project and integrate formatting into CI.

## 2. Package management and dependency locking

- [ ] Choose and document a standard project manifest format and required
  metadata (project name, version, entry point, and YubaLANG compatibility).
- [ ] Define a deterministic lockfile format and when it must be generated or
  updated.
- [ ] Resolve local relative-path dependencies.
- [ ] Resolve dependencies from direct Git URLs, including a reproducible
  revision in the lockfile.
- [ ] Add commands to initialize a project, resolve/install dependencies, and
  verify the lockfile without modifying it.
- [ ] Validate malformed manifests, unavailable sources, conflicting
  requirements, and changed dependency revisions with actionable errors.
- [ ] Document a minimal project and a project using both path and Git
  dependencies.

### Library and import support

- [ ] Define source-level import syntax so programs can import and use library
  code, including a clear rule for namespacing and exported symbols.
- [ ] Implement loading and execution of imported local modules in YubaLANG
  programs, with useful errors for missing modules and import cycles.
- [ ] Connect source imports to dependencies installed or resolved by the
  package manager, including version/revision consistency with the lockfile.
- [ ] Add package-manager commands to add, remove, install, update, and list
  libraries while keeping the manifest and lockfile consistent.
- [ ] Test and document a project that imports a local library and a managed
  third-party library.

## 3. Developer diagnostics and error quality

- [x] Include source file, line, and column in syntax and runtime diagnostics.
- [x] Highlight the relevant source span and show a concise source snippet.
- [x] Explain errors in human-readable language and include a specific,
  actionable hint where one is known.
- [x] Add “Did you mean?” suggestions for undefined variables and misspelled
  function names.
- [ ] Add typo suggestions for missing imports when import support is
  introduced.
- [x] Keep diagnostics free of internal stack traces for ordinary source
  errors.
- [x] Add regression tests for error locations, highlighted spans, suggestions,
  and diagnostic output.

## 4. Basic testing and interoperability

### Built-in test runner

- [ ] Define a simple test-file convention or test annotation syntax.
- [ ] Add a CLI test command that discovers and runs tests.
- [ ] Report passed, failed, and errored tests with source locations and a
  non-zero exit status on failure.
- [ ] Document test discovery, assertions, setup/teardown expectations, and
  example tests.
- [ ] Add runner tests for discovery, failures, empty suites, and exit codes.

### Minimal C ABI / system bindings

- [ ] Specify the supported C ABI boundary and supported primitive data types.
- [ ] Define safe ownership, lifetime, and error-handling rules for values
  crossing the boundary.
- [ ] Implement a minimal binding path for calling a small C function from
  YubaLANG.
- [ ] Add a small portable example and tests for successful calls, invalid
  signatures, and error propagation.
- [ ] Document platform/compiler requirements and clearly state unsupported
  ABI features.

## Out of scope for 1.2

- [ ] Defer fuzzing infrastructure, a complex refactoring-capable LSP, and
  garbage-collector redesign to a later release (1.3 or beyond).

## Release checks

- [ ] Ensure the 1.2 install, project, format, test, and editor workflows are
  documented from a clean checkout.
- [ ] Run the full automated test suite on supported operating systems.
- [ ] Verify a fresh installation can format, resolve dependencies, and run a
  sample project.
- [ ] Publish migration and compatibility notes for the 1.2 release.
