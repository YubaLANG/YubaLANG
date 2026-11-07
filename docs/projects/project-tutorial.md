# Multi-module project tutorial

This tutorial builds and tests a project with a local package dependency, then
adds a registry dependency through YubaPKG. YubaLANG 1.3 accepts manifests
targeting runtime 1.2 or 1.3 and reads lockfile formats 1, 2, and 3. YubaPKG
accepts both manifest versions and writes format 3, which YubaLANG 1.3 can
read offline.

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
## Add a registry dependency with YubaPKG

YubaLANG manages local path and Git dependencies. Registry packages are
resolved and installed by YubaPKG. No public registry is operated by this
project; use a package name and API that exist on your trusted registry.

Install YubaPKG separately, then configure its trusted HTTPS registry URL:

```powershell
python -m pip install -e path\to\YubaPKG
$env:YUBAPKG_REGISTRY_URL = "https://packages.example.org"
```

In `hello_app`, add a package published by that registry. This example assumes
the package is named `text_utils` and exports `greet`:

```text
yubapkg package add text_utils --registry "^1.2.0"
yubapkg package install
yubapkg package check
```

Change `hello_app/main.yl` to import and call that package's documented API,
then run and test the project as before:

```hl
import text_utils
func call text_utils.greet "Ada"
```

The lockfile records the exact registry release, hashes, and complete
transitive dependency graph. After the first install, restore without network
access and validate the committed lock:

```text
yubapkg package install --offline
yubapkg package install --frozen
YubaLANG run .
YubaLANG test tests/cases
```

YubaLANG imports the installed lock graph without contacting the registry.
See the [package guide](package-manager.md) for registry configuration,
compatibility, and security details.
