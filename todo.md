# YubaLANG Roadmap - 1.3.0 and Beyond

This replaces the old 1.2 release checklist. It is a feature backlog, not a
promise that every long-term item ships in 1.3.0. P0 items are the proposed
1.3.0 release gate; P1 items are follow-on work to prioritize after that
release. Keep language/runtime responsibilities separate from YubaPKG:
YubaPKG resolves, downloads, and installs dependencies; YubaLANG executes
programs and imports installed packages.

## P0 - 1.3.0 package-manager integration

- [ ] Specify and version the interface between YubaLANG and YubaPKG:
  manifest compatibility, lockfile format, installed-package layout, and
  runtime version requirements.
- [ ] Make project imports consume the complete locked dependency graph,
  including transitive packages, without contacting the network.
- [ ] Ensure imports resolve to the exact package versions and locations in
  the lockfile; report missing, modified, or inconsistent installations
  with actionable diagnostics.
- [ ] Preserve local module, path dependency, and Git dependency behavior
  while introducing registry-installed packages.
- [ ] Define deterministic import precedence, package namespace rules,
  duplicate-name behavior, and cycle diagnostics across dependency graphs.
- [ ] Add cross-repository tests that use YubaPKG to install a package graph,
  then run imports with YubaLANG both online and offline.
- [ ] Document the end-to-end workflow for installing YubaLANG and YubaPKG,
  creating a project, adding dependencies, running, and reproducing an
  install from a lockfile.

## P0 - Language correctness and specification

- [ ] Publish a versioned 1.3 language reference that defines current
  behavior precisely, including syntax, evaluation order, scoping, types,
  errors, imports, and compatibility guarantees.
- [ ] Define a formal grammar for commands, blocks, function definitions,
  literals, identifiers, comments, and line continuation before adding
  syntax that could conflict with existing programs.
- [ ] Replace scattered parsing and token splitting with a shared tokenizer
  and parser that produce source-located syntax nodes; preserve 1.2 behavior
  with compatibility tests.
- [ ] Define expression precedence and associativity, then add consistent
  parenthesized expressions, unary operators, arithmetic, comparisons, and
  boolean operators.
- [ ] Add expression-level assignment and return values without changing
  existing command forms unexpectedly.
- [ ] Specify integer, floating-point, string, boolean, null/none, and
  collection semantics, including overflow, equality, truthiness, and
  conversion rules.
- [ ] Specify variable declaration, reassignment, shadowing, function
  parameters, and module scope consistently.
- [ ] Turn every documented syntax rule and built-in into executable
  conformance tests with clear negative cases.

## P1 - Core language capabilities

### Functions, modules, and data modeling

- [ ] Add explicit lexical scopes for functions and blocks, with predictable
  variable lifetime and no accidental global leakage.
- [ ] Support closures and first-class functions with defined capture and
  lifetime semantics.
- [x] Expand function parameters to support named arguments and defaults with
  defined ordering, duplicate, and missing-argument rules.
- [x] Add a final `*name` parameter that collects extra positional arguments
  into a tuple.
- [ ] Add a documented export/visibility model for modules instead of
  relying only on all-functions-visible namespace behavior.
- [x] Add user-defined records with typed field access, construction, and
  structural equality; defer class-based extensions until semantics are set.
- [x] Document record mutation and aliasing semantics.
- [ ] Evaluate class-based object orientation only after record, method,
  visibility, inheritance, and initialization semantics are designed.
- [ ] Add collection indexing, safe mutation, slicing, iteration protocols,
  and predictable behavior for missing keys and out-of-range indexes.
- [ ] Define immutable values and copying/reference behavior for collections.

### Types and errors

- [x] Design an opt-in static type-checking command with source-located
  diagnostics and gradual adoption; keep runtime checks where static
  information is unavailable.
- [x] Add an opt-in `check` command and editor diagnostics for statically
  detectable mismatches, while leaving dynamic cases to runtime.
- [x] Define type inference from literals, annotations, and known command
  results; support union/optional, function, and generic collection types.
- [x] Add structured language exceptions with throw, catch, finally, and
  source-located call frames for uncaught errors.
- [x] Define cleanup for current resources: files close automatically at
  program completion, with an explicit close command.
- [ ] Add deterministic cleanup when resource-backed iterators or native
  resource types are introduced.
- [x] Track opened files across function scopes, close them at file-run
  completion, and add an explicit `close` command.
- [x] Add assertions usable for function preconditions and postconditions.
- [x] Add a source-located `assert <boolean> [message]` command.
- [x] Check runtime result assignments against destination variable types,
  allowing integer-to-float widening.

### Standard library and platform APIs

- [ ] Establish a versioned standard-library organization and API stability
  policy.
- [ ] Add path and filesystem utilities with cross-platform path semantics,
  safe file operations, and clear encoding behavior.
- [ ] Add date/time, random, math, structured-data, and text-encoding modules
  with deterministic test seams where appropriate.
- [ ] Add process arguments, environment access, exit codes, and subprocess
  APIs with explicit error handling.
- [ ] Add a documented HTTP/client API only after timeout, TLS, redirect,
  response-size, and credential-handling rules are specified.
- [ ] Define whether asynchronous I/O is needed before expanding networking
  or concurrent APIs.

### Runtime and performance

- [x] Profile representative startup, function, arithmetic, collection, and
  traced-memory workloads with reproducible baselines.
- [x] Add reproducible startup, function, arithmetic, collection, and traced
  memory measurements.
- [ ] Reduce interpreter dispatch overhead without changing program output or
  diagnostics.
- [x] Cache immutable command-tokenization results and add an in-process
  benchmark to measure interpreter execution separately from Python startup.
- [x] Define and test the function recursion limit, large collection behavior,
  and resource-exhaustion diagnostics.
- [x] Enforce a 128-call user-function depth limit with a source-located
  diagnostic.
- [x] Report caught memory exhaustion as a source diagnostic with a
  collection-sizing hint.
- [x] Add reproducible startup and function-call benchmark baselines.
- [ ] Consider bytecode or a cached intermediate representation only if
  representative benchmarks demonstrate a benefit and cache invalidation can
  be made robust.
- [x] Document the trust boundary for imported modules and native libraries;
  never imply that running third-party packages is sandboxed.
- [x] Document that imported code runs with the program's privileges and is
  not sandboxed.
- [x] Specify the current FFI ABI, ownership limitations, error propagation,
  and supported platforms before broadening native interop.
- [ ] Consider a safe extension mechanism for non-C host integrations only
  after the C ABI is stable.

## P1 - Developer tools

### Editor and language server

- [x] Add completion for commands, types, variables, and functions.
- [x] Add signature help, references, rename, document symbols, and
  workspace symbols for open documents.
- [x] Add a quick fix for misspelled command names.
- [x] Reject stale document versions and clear diagnostics/document state on
  close.
- [ ] Support project-aware dependency imports without network activity in
  the language server.
- [x] Test LSP requests and protocol behavior with automated tests.
- [ ] Verify integration in at least one real editor.

### Runtime workflow

- [x] Add a REPL with multiline block entry, persistent session state,
  readable errors, and documented exit/reset behavior.
- [ ] Add debugger hooks for breakpoints, stepping, stack inspection, and
  variable inspection if the runtime execution model can support them
  reliably.
- [x] Extend the test runner with filtering, structured JSON output, and
  unified failure diffs.
- [x] Explain why the process-based runner cannot report source coverage.
- [x] Add a project run command that honors manifest entry points and checks
  installed dependencies against the lockfile.
- [ ] Keep formatter behavior stable; add parser-based formatting tests for
  every newly supported syntax form.

## P1 - Documentation and onboarding

- [ ] Restructure documentation into a beginner path, language reference,
  standard-library reference, project guide, and advanced interoperability
  guides.
- [ ] Add a tutorial that builds and tests a small multi-module project and
  adds a registry dependency through YubaPKG.
- [ ] Add runnable examples for functions, collections, file I/O, error
  handling, modules, testing, and native interop.
- [ ] Document supported Python/runtime platforms, architectures,
  prerequisites, and known limitations.
- [ ] Document deprecations and migration steps for each language/runtime
  release.
- [ ] Ensure documentation examples are checked in CI or exercised by tests.

## P0 - 1.3.0 quality and release

- [ ] Run the complete test suite on Windows, Linux, and macOS for supported
  Python versions.
- [ ] Add CI checks for formatting, packaging, documentation examples, and
  cross-repository YubaPKG integration.
- [ ] Verify clean installation, project initialization, package restore,
  imports, tests, formatting, LSP startup, and native interop where
  supported.
- [ ] Produce reproducible release artifacts and SHA-256 checksums; document
  what checksums do and do not protect against.
- [ ] Maintain an explicit compatibility matrix for YubaLANG, YubaPKG,
  manifest versions, lockfile versions, and package compatibility.
- [ ] Publish 1.3.0 release notes and migration guidance.

## Future major-version candidates

- [ ] Decide whether YubaLANG remains an interpreter-only language or gains
  a compiler/bytecode target; base the decision on measured performance and
  distribution needs.
- [ ] Evaluate concurrency primitives and asynchronous execution with clear
  cancellation, error, and shared-state rules.
- [ ] Evaluate a richer package/build workflow for generated code, native
  dependencies, and reproducible application bundles.
- [ ] Define a long-term language governance and deprecation policy before
  introducing breaking syntax or runtime behavior.
