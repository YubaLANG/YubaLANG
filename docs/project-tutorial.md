# Multi-module project tutorial

This tutorial builds and tests a project with a local package dependency. It
uses the currently supported path-dependency workflow. The public YubaPKG
registry and registry dependencies are not available yet.

## Create the library and app

Install YubaPKG from its [repository](https://github.com/YubaLANG/YubaPKG),
then from an empty working directory create a library and app project:

```text
yubapkg package init hello_library
yubapkg package init hello_app
```

The current YubaPKG release creates manifests targeting YubaLANG 1.2, which
remains accepted by the YubaLANG 1.3 runtime.

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
yubapkg package add hello_library --path ../hello_library
yubapkg package install
yubapkg package check
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

Registry installation, semantic-version selection, and transitive dependency
solving are not implemented in YubaPKG yet. Use direct path or Git sources
until its registry support is released.
