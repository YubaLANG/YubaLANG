# YubaLANG language server

YubaLANG includes a lightweight Language Server Protocol (LSP) server for
`.hl` files. It uses the standard input/output JSON-RPC transport and the
Python standard library; it does not execute the open source file.

## Starting the server

From the repository root, configure an LSP-capable editor to start:

```text
py YubaLANG.py --lsp
```

The server communicates over stdin/stdout. Configure the editor's LSP client
to use that command, associate `.hl` files with YubaLANG, and avoid wrapping
the command in a shell that writes banners to stdout. In VS Code, a generic
LSP client extension is required because VS Code does not include a built-in
client for arbitrary language servers.

## Supported features

- Open, full-document change, and close notifications.
- Syntax diagnostics for malformed quoting, invalid or unknown commands,
  invalid declarations, and unclosed or mismatched blocks.
- Go to definition for declared variables, function parameters, and functions.
- Hover documentation for language commands, built-ins, and types.

Diagnostics and symbol lookup are static and intentionally do not execute
programs. The server currently uses full-document synchronization; editors
should send the complete updated document in each change notification.

## Try it

Open [`examples\functions.hl`](../examples/functions.hl) in an LSP-capable
editor configured to launch the command above. Hover over `func`, `return`,
or `filter`, and use Go to Definition on `is_positive` or `values`.

To verify the stdio server without an editor, run the automated tests from the
repository root:

```text
py -m unittest tests.test_lsp
```
