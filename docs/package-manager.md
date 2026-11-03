# Projects and packages

YubaLANG projects use a dependency-free JSON manifest named `yuba.json` and a
generated `yuba.lock.json`. Both files should be checked into version control.
YubaLANG 1.3 accepts manifests targeting runtime 1.2 or 1.3 and reads lockfile
formats 1, 2, and 3. Format 1 records direct dependencies only; format 2
records the complete path/Git graph; format 3 adds exact registry releases,
artifact hashes, and the complete graph. YubaPKG accepts manifests targeting
runtime 1.2 and 1.3 and writes format 3. The YubaLANG package commands continue
to install path/Git sources; use YubaPKG to install or update registry
dependencies.

The bundled `std.*` modules are supplied by the YubaLANG runtime and are not
package dependencies. They work with YubaLANG and YubaPKG projects without
manifest entries, lockfile changes, or an install step. Both tools continue to
manage path and Git dependencies. Registry packages are managed by YubaPKG;
the YubaLANG runtime can verify and import their installed format-3 lockfiles.

## Create a project

```text
YubaLANG package init
YubaLANG main.yl
```

`package init [directory]` creates a manifest and a starter `main.yl`. A
manifest has the following fields:

```json
{
  "name": "sample",
  "version": "0.1.0",
  "entry": "main.yl",
  "yubalang": "1.3",
  "dependencies": {}
}
```

`name`, `version`, `entry`, and `yubalang` are required strings. Dependencies
are named packages whose source is either a relative path or a Git URL.
YubaLANG 1.3 accepts manifests targeting versions `1.2` and `1.3`; projects
initialized by YubaLANG 1.3 target `"yubalang": "1.3"`. The current YubaPKG
release also supports both manifest versions.

```json
{
  "name": "sample",
  "version": "0.1.0",
  "entry": "main.yl",
  "yubalang": "1.3",
  "dependencies": {
    "local_math": { "path": "../local_math" },
    "text_utils": { "git": "https://github.com/example/text-utils.git" }
  }
}
```

Registry dependencies use a semantic-version range and are resolved by
YubaPKG against the configured trusted registry:

```json
{
  "name": "sample",
  "version": "0.1.0",
  "entry": "main.yl",
  "yubalang": "1.3",
  "dependencies": {
    "text_utils": { "registry": "^1.2.0" }
  }
}
```

Set `YUBAPKG_REGISTRY_URL` to the trusted HTTPS base URL before using a
registry dependency. The package-manager implementation currently supports one
registry endpoint per resolution, and does not provide publishing,
authentication, search, or private registries. See the
[YubaPKG registry protocol](https://github.com/YubaLANG/YubaPKG/blob/main/docs/registry.md).

The path is relative to the project manifest. Each dependency directory must
contain its own `yuba.json`; its `name` must match the dependency key. The
`entry` field identifies the module loaded when a package is imported by name.
Git URLs may optionally include a `rev` field naming a branch or tag:

```json
"text_utils": {
  "git": "https://github.com/example/text-utils.git",
  "rev": "v1.0.0"
}
```

## Manage dependencies

```text
YubaLANG package add local_math --path ../local_math
YubaLANG package add text_utils --git https://github.com/example/text-utils.git
YubaLANG package add text_utils --git https://github.com/example/text-utils.git --rev v1.0.0
YubaLANG package install
YubaLANG package update
YubaLANG package update text_utils
YubaLANG package list
YubaLANG package check
YubaLANG package remove text_utils
YubaLANG run [project-directory] -- first second
```

YubaPKG additionally supports:

```text
yubapkg package add text_utils --registry "^1.2.0"
yubapkg package install --offline
yubapkg package install --frozen
```

`--offline` installs from an existing lock and local caches only.
`--frozen` validates the manifest, lock, and installed packages without
resolving, downloading, or writing.

Arguments after `--` are passed to the project entry point and can be read
with `std.process.args()`. When executing a source file directly, arguments
after the file name are passed the same way.

`add` and `remove` update the manifest and lockfile. `install` recursively
locks dependencies declared by dependencies, preserving previously locked Git
revisions when sources are unchanged. A new Git dependency resolves its
requested revision or the default branch head. Git dependencies are cloned
under `.yuba/packages/<name>` relative to the manifest that declares them and
checked out at the locked commit. `update` refreshes Git revisions (or only the
named direct dependency), except where the manifest explicitly pins `rev`.
Path dependencies always point at the current contents of the specified
directory. Removing a Git dependency updates the manifest and lockfile; its
unused checkout may remain in `.yuba/packages`.

Lockfiles are deterministic JSON. Format 2 records path/Git dependencies;
format 3 records registry version, origin, artifact URL, SHA-256, installed
tree digest, package identity, and a nested `dependencies` object. The same
graph is written to each dependency's own lockfile so imports resolve relative
to that package's manifest. Path dependencies remain live directories and are
not content-addressed; Git packages are pinned to exact commits; registry
packages are verified against cached artifacts and their installed tree.
`package check` is offline and verifies lock consistency and installed
packages. YubaLANG runtime imports accept registry lock entries but do not
perform registry resolution or downloads. Use `yubapkg package install` to
update the lock and install artifacts. Format-1 and format-2 locks are upgraded
by YubaPKG; YubaLANG's own path/Git installer continues to write format 2.

## Import modules

Bundled standard-library imports use the reserved `std.*` namespace and do not
need a dependency declaration:

```hl
import std.path as path
import std.json as json

define var file_name: string = ""
func call path.join "config" "app.json" -> file_name
```

They are provided by the runtime, so they also work after a locked offline
install and do not add entries to `yuba.lock.json`. The complete module
inventory and compatibility policy are in the
[standard-library reference](standard-library.md).

An import matching a bundled `std.*` module resolves to the runtime library
first. Other imports are relative to the importing source file, unless the
first name is a declared package dependency:

```hl
import helpers
import local_math as math

define var answer: int = 0
func call math.add 20 22 -> answer
text output answer
```

For a non-standard import, a dependency declared in the nearest package
manifest takes precedence over a local file with the same first name. Otherwise, `helpers`
resolves to `helpers.yl` or `helpers/main.yl` beside the importing file.
Dotted imports follow directories, for example `import tools.math` resolves
to `tools/math.yl` or `tools/math/main.yl`; without an explicit alias its
namespace is `math`. For a package import, the manifest's `entry` is used.
Dependencies of imported packages resolve from that package's own manifest
and locked graph, including transitive path, Git, and installed registry
packages. Imports are
loaded once per run. Dependency cycles are reported during installation or
validation; module-import cycles are errors at runtime.

Module-level functions are public by default and available through the
namespace; `func call namespace.function` is the call form. A module can mark
a helper private with `func private define helper ... endfunc`. Private
functions remain callable from the module's other functions but are not
available to importers. Module top-level commands run once when imported, and
variables declared there use the interpreter's shared global scope. An `as`
alias must be a valid identifier.

Missing modules and package/lockfile problems are reported with an actionable
source diagnostic or package-manager error. Runtime imports use the checked
lock graph and do not access the network; run `package install` beforehand.
Within one runtime, rebinding a namespace to a different module is an error.
Importing a module executes its top-level commands. Imported code runs with
the program's privileges; YubaLANG does not sandbox modules or dependencies,
so only use source code from packages you trust. YubaPKG supports path, Git, and static registry sources, including recursive
graphs and semantic-version ranges. A public registry service and publishing
workflow are not provided.
