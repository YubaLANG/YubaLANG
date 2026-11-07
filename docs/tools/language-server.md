# YubaLANG language server

YubaLANG includes a lightweight Language Server Protocol (LSP) server for
`.yl` files. It uses the standard input/output JSON-RPC transport and the
Python standard library; it does not execute the open source file.

## Starting the server

From the repository root, configure an LSP-capable editor to start:

```text
py YubaLANG.py --lsp
```

The server communicates over stdin/stdout. Configure the editor's LSP client
to use that command, associate `.yl` files with YubaLANG, and avoid wrapping
the command in a shell that writes banners to stdout. In VS Code, a generic
LSP client extension is required because VS Code does not include a built-in
client for arbitrary language servers.

## Supported features

- Open, full-document and ranged change, and close notifications.
- Syntax diagnostics for malformed quoting, invalid or unknown commands,
  invalid declarations, and unclosed or mismatched blocks.
- Project import diagnostics using the nearest manifest and checked lockfile;
  dependency resolution is local and does not access the network.
- Go to definition for declared variables, function parameters, and functions.
- Go to definition, hover, completion, signature help, and workspace symbols
  for public functions in imported project dependencies.
- Hover documentation for language commands, built-ins, and types.
- Completion for commands, types, and symbols in open documents and
  namespaced project dependency functions.
- Signature help for user-defined functions and imported project functions.
- Find references and rename for symbols in open documents.
- Document and workspace symbol search.
- Quick fixes for misspelled command names.
- Incremental document changes with stale-version rejection.

Diagnostics and symbol lookup are static and intentionally do not execute
programs. Editors may send full or ranged document changes with monotonically
increasing versions. Rename and references are limited to open documents;
unopened files are not searched or changed. Project imports are resolved
against the nearest project's checked lockfile and installed package contents.
Unavailable imports produce diagnostics, and resolution never downloads
packages. Dependency symbols are read-only. Completion and signature help are
best-effort suggestions, not a complete semantic type engine.

## Try it

Open [`examples\functions.yl`](../../examples/functions.yl) in an LSP-capable
editor configured to launch the command above. Hover over `func`, `return`,
or `filter`; try completion, signature help, references, and rename on
`is_positive` or `values`.

To verify the stdio server without an editor, run the automated tests from the
repository root:

```text
py -m unittest tests.test_lsp
```
