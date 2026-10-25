# Multi-module project tutorial

This tutorial builds and tests a project with a local package dependency. It
uses the YubaLANG 1.3 package interface, including lockfile format 2. The
external YubaPKG release documents YubaLANG 1.2 manifest compatibility, but
its support for lockfile format 2 must be confirmed before managing this
project with that tool.

## Create the library and app

From an empty working directory create a library and app project:

```text
YubaLANG package init hello_library
YubaLANG package init hello_app
```

YubaLANG 1.3 creates manifests targeting runtime 1.3. Manifests targeting
runtime 1.2 are also accepted.

Replace `hello_library/main.yl` with:

```hl
func define greet name
    text output "Hello"
    text output name
endfunc
```

Replace `hello_app/main.yl` with:

```hl
import hello_library
func call hello_library.greet "Ada"
```

## Add and install the dependency

From the app directory, add the library as a local path dependency:

```text
YubaLANG package add hello_library --path ../hello_library
YubaLANG package install
YubaLANG package check
```

The dependency key must match the library manifest's `name`. The lockfile
records the relative path; path dependencies use the current directory
contents and are not copied into the package cache.

## Run and test the app

From `hello_app`, run:

```text
YubaLANG run .
```

The program prints `Hello` and `Ada` on separate lines. Add an output test
at `hello_app/tests/cases/greeting.yl`:

```hl
import hello_library
func call hello_library.greet "Ada"
```

Create `hello_app/tests/cases/greeting.expected.txt` containing:

```text
Hello
Ada
```

Then run `YubaLANG test tests/cases`. The runner compares exact standard
output, including line breaks.

YubaLANG recursively locks path and Git dependencies declared by packages.
Registry installation and semantic-version range selection are not supported.
