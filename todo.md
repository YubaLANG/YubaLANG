# YubaLANG 1.4 roadmap

This is a proposed planning checklist, not a commitment that every candidate
will ship in 1.4. Promote a candidate into the release scope only after its
design, compatibility impact, and implementation size are understood. Keep
YubaLANG runtime responsibilities separate from YubaPKG package resolution
and installation.

## Release foundations

- [ ] Agree on the 1.4 scope and publish the accepted feature set before
  implementation.
- [ ] Review open defects and user requests; prioritize by impact and
  reproducibility rather than adding speculative syntax.
- [ ] Turn every documented language rule and built-in into executable
  conformance tests, including negative cases and source diagnostics.
- [ ] Verify language, runtime, formatter, test runner, and LSP behavior
  together for every accepted language change.
- [ ] Run the complete test suite and release smoke tests on supported
  Windows, Linux, and macOS targets.
- [ ] Update the 1.4 language reference, master reference, migration notes,
  examples, and release notes for all shipped changes.
- [ ] Publish release artifacts and checksums, and verify clean installation,
  project restore/import, tests, formatting, LSP startup, and supported
  native-interoperability scenarios.

## Feature candidates

### Language and data model

- [ ] Design record methods, default field values, and construction rules.
  Specify receiver semantics, mutation, visibility, equality, and
  compatibility before choosing syntax.
- [ ] Improve static type analysis where it can provide reliable value:
  document inference limits, add focused rules, and test that diagnostics do
  not reject valid dynamic programs.
- [ ] Evaluate richer expression forms, such as function calls in
  expressions, only with a grammar proposal and compatibility tests; current
  function calls remain commands.

### Runtime and resource lifecycle

- [ ] Design a general deterministic resource-lifecycle protocol before
  adding APIs that return resources or resource-backed iterators.
- [ ] Decide whether concurrency and asynchronous I/O address concrete user
  needs. If accepted, first specify cancellation, error propagation,
  scheduling, and shared mutable state; implement async APIs only after those
  semantics are testable.

### Developer experience

- [ ] Evaluate an interactive debugger frontend over the existing debugger
  hooks, including stepping, breakpoints, stack inspection, and variables.
- [ ] Evaluate source-level test coverage instrumentation and report format;
  the current process-based output test runner does not collect coverage.
- [ ] Evaluate an LSP workspace index for unopened files, including indexing
  performance, invalidation, and rename safety.
- [ ] Verify the language server in at least one real editor and document the
  supported setup.

### Projects and distribution

- [ ] Gather concrete use cases for building or bundling applications with
  generated code or native dependencies; define reproducibility and platform
  requirements before designing a command.
- [ ] Keep registry resolution and installation in YubaPKG. If the
  YubaLANG/YubaPKG interface changes, update the compatibility matrix and
  cross-tool integration tests.

## Explicitly gated work

- Bytecode or compiler targets are not a 1.4 goal by default. Reconsider only
  if representative benchmarks or distribution requirements demonstrate a
  measurable need.
- Class-based object orientation, inheritance, and a non-C plugin system are
  not assumed. Require concrete use cases and a separate semantics and safety
  proposal before adding them.
- Broader native FFI types are not assumed. Any proposal must specify ABI
  behavior, ownership, platform support, and process-safety limitations.

## Completion criteria

A 1.4 change is complete only when its behavior is specified, tested,
documented in the versioned and master references, covered by migration
guidance when compatibility is affected, and validated on the platforms
required by its scope.

See the [long-term YubaLANG feature backlog](docs/roadmap/features.md) for
candidates that may fall outside 1.4.
