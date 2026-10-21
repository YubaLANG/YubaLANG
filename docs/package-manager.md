# Projects and packages

YubaLANG projects use a dependency-free JSON manifest named `yuba.json` and a
generated `yuba.lock.json`. Both files should be checked into version control.

## Create a project

```text
YubaLANG package init
YubaLANG main.hl
```

`package init [directory]` creates a manifest and a starter `main.hl`. A
manifest has the following fields:

```json
{
  "name": "sample",
  "version": "0.1.0",
  "entry": "main.hl",
  "yubalang": "1.2",
  "dependencies": {}
}
```

`name`, `version`, `entry`, and `yubalang` are required strings. Dependencies
are named packages whose source is either a relative path or a Git URL:
the runtime currently accepts `"yubalang": "1.2"`.

```json
{
  "name": "sample",
  "version": "0.1.0",
  "entry": "main.hl",
  "yubalang": "1.2",
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

`add` and `remove` update the manifest and lockfile. `install` preserves
previously locked Git revisions when the manifest source is unchanged; for a
new Git dependency it resolves the default branch head. Git dependencies are
cloned under `.yuba/packages/<name>` and checked out at the locked commit.
`update` refreshes Git revisions (or only the named dependency), except where
the manifest explicitly pins `rev`. Path dependencies always point at the
current contents of the specified directory. Removing a Git dependency updates
the manifest and lockfile; its unused checkout may remain in `.yuba/packages`.

The lockfile is deterministic JSON. It records each dependency source and, for
Git sources, the resolved commit ID. `package check` verifies that the
manifest and lockfile agree, path dependencies exist, and cached Git checkouts
are at their locked revisions; it does not contact Git remotes or modify
files. Run `package install` after editing a manifest. Git must be installed
and the selected Git source must be reachable when adding or installing a
dependency.

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

For a local import, `helpers` resolves to `helpers.hl` or `helpers/main.hl`
beside the importing file. Dotted imports follow directories, for example
`import tools.math` resolves to `tools/math.hl` or
`tools/math/main.hl`; without an explicit alias its namespace is `math`. For a
dependency import, the package manifest's `entry` is used. Imports are loaded
once per run. A cycle is an error.

All functions declared in a module are available through its namespace;
`func call namespace.function` is the call form. A function can call another
function in its own module without repeating the namespace. Module top-level
commands run once when imported, and variables declared there use the
interpreter's shared global scope. Use function-local variables for library
implementation details. An `as` alias must be a valid identifier.

Missing modules and package/lockfile problems are reported with an actionable
source diagnostic or package-manager error. Importing a module executes its
top-level commands, so only use source code from packages you trust. YubaLANG
currently supports direct path and Git dependencies only; it does not have a
public package registry, version-range solver, or transitive dependency
resolver.
