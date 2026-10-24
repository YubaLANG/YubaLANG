# YubaLANG
A fast programming language with a hierarchical syntax built for modern programming.

## Documentation

* [Master feature reference](docs/master-reference.md)
* [YubaLANG 1.2 language reference](docs/1.2-docs.md)
* [Built-in function reference](docs/builtins.md)
* [Language server and editor setup](docs/language-server.md)
* [Formatting YubaLANG source files](docs/formatter.md)
* [Installing YubaLANG](docs/install.md)
* [Projects, imports, and package management](docs/package-manager.md)
* [Calling C functions](docs/c-abi.md)
* [Runnable example programs](examples/)
* [Runtime performance benchmarks](docs/performance.md)

Run `py -3 YubaLANG.py check <file.yl>` for non-executing syntax and
statically-detectable type diagnostics.
The [language reference](docs/1.2-docs.md#records) describes user-defined
records.

For projects, run `py -3 YubaLANG.py run .`; for an interactive session, run
`py -3 YubaLANG.py repl`.

## License

YubaLANG is available under the custom [Yuba Non-Commercial Software
License](LICENSE). It permits copying, modification, and redistribution for
non-commercial purposes with attribution. Commercial use requires prior
written permission. This is a source-available license, not an OSI-approved
open-source license.