# YubaLANG
A fast programming language with a hierarchical syntax built for modern programming.

## Documentation

* [Getting started](docs/getting-started.md)
* [Documentation guide](docs/index.md)
* [Master feature reference](docs/master-reference.md)
* [YubaLANG 1.3 language reference](docs/1.3-docs.md)
* [Built-in function reference](docs/builtins.md)
* [Standard-library organization and API policy](docs/standard-library.md)
* [Language server and editor setup](docs/language-server.md)
* [Formatting YubaLANG source files](docs/formatter.md)
* [Installing YubaLANG](docs/install.md)
* [Projects, imports, and package management](docs/package-manager.md)
* [Calling C functions](docs/c-abi.md)
* [Runnable example programs](examples/)
* [Runtime performance benchmarks](docs/performance.md)
* [1.2 to 1.3 migration notes](docs/1.3-migration.md)
* [1.3.0 release notes](docs/1.3-release-notes.md)

New to YubaLANG? Follow the [getting-started guide](docs/getting-started.md)
to create, check, and run a first program. From a source checkout, run
`py -3 YubaLANG.py check <file.yl>` for non-executing syntax and
statically-detectable type diagnostics. For projects, run
`py -3 YubaLANG.py run .`; for an interactive session, run
`py -3 YubaLANG.py repl`.

## License

YubaLANG is available under the custom [Yuba Non-Commercial Software
License](LICENSE). It permits copying, modification, and redistribution for
non-commercial purposes with attribution. Commercial use requires prior
written permission. This is a source-available license, not an OSI-approved
open-source license.