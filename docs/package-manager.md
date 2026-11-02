# Projects and packages

YubaLANG projects use a dependency-free JSON manifest named `yuba.json` and a
generated `yuba.lock.json`. Both files should be checked into version control.
YubaLANG 1.3 accepts manifests targeting runtime 1.2 or 1.3 and reads lockfile
formats 1 and 2. Format 1 records direct dependencies only; format 2 records
the complete nested graph and is written by both YubaLANG and YubaPKG. YubaPKG
accepts manifests targeting runtime 1.2 and 1.3. Use either package manager to
install dependencies and generate a complete format-2 graph.

The bundled `std.*` modules are supplied by the YubaLANG runtime and are not
package dependencies. They work with YubaLANG and YubaPKG projects without
manifest entries, lockfile changes, or an install step. Both tools continue to
manage third-party path and Git dependencies; registry and semantic-version
range resolution are not implemented.

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

Lockfile format 2 is deterministic JSON. Every dependency entry records its
source, resolved path or Git commit, package identity (`name`, `version`,
`entry`, and `yubalang`), and a nested `dependencies` object containing that
package's complete locked dependency graph. The same graph is written to each
dependency's own lockfile so imports from that package can resolve
dependencies relative to its manifest. Path dependencies remain live
directories and are not content-addressed; their location and declared
identity are locked, while local source changes remain visible. Git packages
are pinned to their exact commit. `package check` verifies manifests, nested
lockfiles, package identities and entry files, and locked Git checkouts,
including modified tracked files and untracked source files (excluding the
manager's generated lockfile and nested cache). It does not contact Git
remotes or modify files. Legacy format-1 lockfiles are accepted for direct
dependency checks and imports, but do not capture nested graphs or package
identities; run `package install` to upgrade them to format 2. Both package
managers write format 2 and lock the complete graph. Git must be installed and
reachable when installing a new or updated Git dependency.

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
and locked graph, including transitive path and Git packages. Imports are
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
so only use source code from packages you trust. The package tools support
direct path and Git sources, including recursively declared dependency
graphs; there is not yet a public registry or semantic-version range solver.
