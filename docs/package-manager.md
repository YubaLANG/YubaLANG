# Projects and packages

YubaLANG projects use a dependency-free JSON manifest named `yuba.json` and a
generated `yuba.lock.json`. Both files should be checked into version control.
YubaLANG 1.3 accepts manifests targeting runtime 1.2 or 1.3. The package
interface uses lockfile format version 2; package tools must preserve the
declared sources and the complete nested graph in that format. The current
external YubaPKG release documents YubaLANG 1.2 manifest compatibility; its
support for lockfile format 2 should be verified before using it to manage a
YubaLANG 1.3 project.

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
release documents compatibility with YubaLANG 1.2, so check its manifest
reference before using a 1.3-targeted manifest with that tool.

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
```

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
remotes or modify files. Run `package install` after changing a manifest or
moving a path dependency. A format-1 lockfile must be regenerated with
`package install`. Git must be installed and reachable when installing a new
or updated Git dependency.

## Import modules

An import is relative to the importing source file, unless the first name is a
declared package dependency:

```hl
import helpers
import local_math as math

define var answer: int = 0
func call math.add 20 22 -> answer
text output answer
```

For an import, a dependency declared in the nearest package manifest takes
precedence over a local file with the same first name. Otherwise, `helpers`
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
