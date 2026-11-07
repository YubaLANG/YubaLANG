# YubaLANG
A fast programming language with a hierarchical syntax built for modern programming.

## Documentation

Start with the [documentation guide](docs/index.md) to choose a path.

### Learn the language

- [Getting started](docs/getting-started.md)
- [YubaLANG 1.3 language reference](docs/1.3-docs.md)
- [Master feature reference](docs/master-reference.md)
- [Built-in function reference](docs/builtins.md)
- [Standard library](docs/standard-library.md)
- [Runnable example catalog](docs/examples.md)

### Build projects and use tools

- [Projects, imports, and package management](docs/package-manager.md)
- [Multi-module project tutorial](docs/project-tutorial.md)
- [Formatting source files](docs/formatter.md)
- [Language server and editor setup](docs/language-server.md)
- [Installation](docs/install.md)

### Interoperability and release history

- [Calling C functions](docs/c-abi.md)
- [Runtime performance](docs/performance.md)
- [1.2 to 1.3 migration notes](docs/1.3-migration.md)
- [1.3.0 release notes](docs/1.3-release-notes.md)

From a source checkout, run `py -3 YubaLANG.py check <file.yl>` for
non-executing syntax and statically detectable type diagnostics. For projects,
run `py -3 YubaLANG.py run .`; for an interactive session, run
`py -3 YubaLANG.py repl`.

## License

YubaLANG is available under the custom [Yuba Non-Commercial Software
License](LICENSE). It permits copying, modification, and redistribution for
non-commercial purposes with attribution. Commercial use requires prior
written permission. This is a source-available license, not an OSI-approved
open-source license.