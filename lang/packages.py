"""Project manifests, dependency locking, and package-manager commands."""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


MANIFEST_NAME = "yuba.json"
LOCK_NAME = "yuba.lock.json"
LOCK_VERSION = 2
SUPPORTED_YUBALANG = "1.3"
COMPATIBLE_YUBALANG_VERSIONS = {"1.2", SUPPORTED_YUBALANG}
PACKAGE_CACHE = Path(".yuba") / "packages"
_PACKAGE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
_COMMIT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class PackageError(ValueError):
    """An actionable project or dependency error."""


def find_project_root(path: Path) -> Path | None:
    path = path.resolve()
    if path.is_file():
        path = path.parent
    for candidate in (path, *path.parents):
        if (candidate / MANIFEST_NAME).is_file():
            return candidate
    return None


def read_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise PackageError(f"Cannot read manifest '{path}': {error}") from error
    except UnicodeError as error:
        raise PackageError(f"Manifest '{path}' is not valid UTF-8: {error}") from error
    except json.JSONDecodeError as error:
        raise PackageError(
            f"Invalid JSON in '{path}' at line {error.lineno}, column {error.colno}: "
            f"{error.msg}"
        ) from error
    if not isinstance(data, dict):
        raise PackageError(f"Manifest '{path}' must contain a JSON object.")
    for field in ("name", "version", "entry", "yubalang"):
        if not isinstance(data.get(field), str) or not data[field]:
            raise PackageError(f"Manifest '{path}' requires a non-empty '{field}' string.")
    if data["yubalang"] not in COMPATIBLE_YUBALANG_VERSIONS:
        raise PackageError(
            f"Manifest '{path}' requires YubaLANG {data['yubalang']}; "
            f"this runtime supports 1.2 and {SUPPORTED_YUBALANG}."
        )
    dependencies = data.setdefault("dependencies", {})
    if not isinstance(dependencies, dict):
        raise PackageError(f"Manifest '{path}' field 'dependencies' must be an object.")
    for name, source in dependencies.items():
        _validate_name(name)
        _validate_source(name, source)
    return data


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or not _PACKAGE_NAME.fullmatch(name):
        raise PackageError(
            f"Invalid package name '{name}'; use a letter followed by letters, "
            "digits, underscores, or hyphens."
        )


def _validate_source(name: str, source: Any) -> None:
    if not isinstance(source, dict) or len(source) not in (1, 2):
        raise PackageError(
            f"Dependency '{name}' must specify either {{'path': ...}} "
            "or {{'git': ..., 'rev': ...}}."
        )
    if "path" in source:
        if len(source) != 1 or not isinstance(source["path"], str) or not source["path"]:
            raise PackageError(f"Dependency '{name}' has an invalid path source.")
    elif "git" in source:
        if not isinstance(source["git"], str) or not source["git"]:
            raise PackageError(f"Dependency '{name}' has an invalid Git URL.")
        if set(source) - {"git", "rev"}:
            raise PackageError(f"Dependency '{name}' has unsupported Git source fields.")
        if "rev" in source and (
            not isinstance(source["rev"], str) or not source["rev"]
        ):
            raise PackageError(f"Dependency '{name}' has an invalid Git revision.")
    else:
        raise PackageError(
            f"Dependency '{name}' must specify either a 'path' or 'git' source."
        )


def read_lockfile(root: Path) -> dict[str, Any]:
    path = root / LOCK_NAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise PackageError(
            f"Lockfile '{path}' is missing or unreadable; run 'YubaLANG package install'."
        ) from error
    except UnicodeError as error:
        raise PackageError(f"Lockfile '{path}' is not valid UTF-8: {error}") from error
    except json.JSONDecodeError as error:
        raise PackageError(
            f"Invalid JSON in '{path}' at line {error.lineno}, column {error.colno}: "
            f"{error.msg}"
        ) from error
    if (
        not isinstance(data, dict)
        or data.get("lock_version") != LOCK_VERSION
        or not isinstance(data.get("dependencies"), dict)
    ):
        raise PackageError(
            f"Unsupported or malformed lockfile '{path}'; run 'YubaLANG package install'."
        )
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    try:
        path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise PackageError(f"Cannot write '{path}': {error}") from error


def _git(root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as error:
        raise PackageError(f"Cannot run Git: {error}") from error
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise PackageError(f"Git {' '.join(arguments)} failed: {detail}")
    return result.stdout.strip()


def _resolve_git_revision(url: str, requested: str | None) -> str:
    reference = requested or "HEAD"
    result = _git(Path.cwd(), "ls-remote", url, reference, f"{reference}^{{}}")
    revisions = [
        line.split() for line in result.splitlines() if len(line.split()) == 2
    ]
    peeled = [revision for revision, ref in revisions if ref.endswith("^{}")]
    matching = [revision for revision, _ in revisions]
    revision = (peeled or matching or [None])[0]
    if revision is None:
        raise PackageError(f"Git source '{url}' has no revision matching '{reference}'.")
    if not _COMMIT_ID.fullmatch(revision):
        raise PackageError(f"Git source '{url}' returned an invalid commit ID.")
    return revision


def _dependency_lock(
    root: Path,
    name: str,
    source: dict[str, str],
    old_entry: dict[str, Any] | None,
    update: bool,
) -> dict[str, Any]:
    if "path" in source:
        path = (root / source["path"]).resolve()
        if not path.is_dir():
            raise PackageError(f"Path dependency '{name}' does not exist: {path}")
        if not (path / MANIFEST_NAME).is_file():
            raise PackageError(f"Path dependency '{name}' has no {MANIFEST_NAME}: {path}")
        relative_path = Path(source["path"]).as_posix()
        return {
            "source": source,
            "resolved": {"path": relative_path},
        }

    url = source["git"]
    old_source = old_entry.get("source") if isinstance(old_entry, dict) else None
    old_resolved = old_entry.get("resolved") if isinstance(old_entry, dict) else None
    if (
        not update
        and source.get("rev") is None
        and old_source == {"git": url}
        and isinstance(old_resolved, dict)
        and isinstance(old_resolved.get("rev"), str)
        and _COMMIT_ID.fullmatch(old_resolved["rev"])
    ):
        revision = old_resolved["rev"]
    else:
        revision = _resolve_git_revision(url, source.get("rev"))
    lock_source = {"git": url}
    if "rev" in source:
        lock_source["rev"] = source["rev"]
    return {"source": lock_source, "resolved": {"rev": revision}}


def _install_git(root: Path, name: str, url: str, revision: str) -> Path:
    if not _COMMIT_ID.fullmatch(revision):
        raise PackageError(f"Lockfile has an invalid Git revision for dependency '{name}'.")
    destination = root / PACKAGE_CACHE / name
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise PackageError(f"Cannot create package cache '{destination.parent}': {error}") from error
    if (destination / ".git").is_dir():
        origin = _git(destination, "remote", "get-url", "origin")
        if origin != url:
            _git(destination, "remote", "set-url", "origin", url)
        _git(destination, "fetch", "--quiet", "origin")
    elif destination.exists():
        raise PackageError(
            f"Package cache path exists but is not a Git checkout: {destination}"
        )
    else:
        _git(root, "clone", "--quiet", "--no-checkout", url, str(destination))
    _git(destination, "checkout", "--quiet", "--detach", revision)
    if not (destination / MANIFEST_NAME).is_file():
        raise PackageError(f"Git dependency '{name}' has no {MANIFEST_NAME}.")
    return destination


def install(root: Path, update: bool | set[str] = False) -> dict[str, Any]:
    return _install(root.resolve(), update, [])


def _install(
    root: Path,
    update: bool | set[str],
    package_stack: list[str],
    locked_dependencies: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = read_manifest(root)
    package_name = manifest["name"]
    if package_name in package_stack:
        cycle = " -> ".join((*package_stack, package_name))
        raise PackageError(f"Dependency cycle detected: {cycle}.")
    package_stack = [*package_stack, package_name]
    dependencies = manifest["dependencies"]
    old_lock_path = root / LOCK_NAME
    try:
        old_lock = json.loads(old_lock_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        old_lock = {}
    old_dependencies = (
        locked_dependencies
        if locked_dependencies is not None
        else old_lock.get("dependencies", {})
    )
    if not isinstance(old_dependencies, dict):
        old_dependencies = {}

    locked: dict[str, Any] = {}
    for name in sorted(dependencies):
        source = dependencies[name]
        entry = _dependency_lock(
            root,
            name,
            source,
            old_dependencies.get(name),
            update is True or isinstance(update, set) and name in update,
        )
        locked[name] = entry
        resolved = entry["resolved"]
        if "path" in resolved:
            dependency_root = (root / resolved["path"]).resolve()
        else:
            dependency_root = _install_git(
                root, name, source["git"], resolved["rev"]
            )
        dependency_manifest = read_manifest(dependency_root)
        if dependency_manifest["name"] != name:
            raise PackageError(
                f"Dependency '{name}' points to package "
                f"'{dependency_manifest['name']}' at {dependency_root}."
            )
        resolve_entry(dependency_root, dependency_manifest)
        entry["package"] = {
            field: dependency_manifest[field]
            for field in ("name", "version", "entry", "yubalang")
        }
        dependency_lock = _install(
            dependency_root,
            False,
            package_stack,
            entry.get("dependencies")
            if isinstance(entry.get("dependencies"), dict)
            else None,
        )
        entry["dependencies"] = dependency_lock["dependencies"]

    lock = {"lock_version": LOCK_VERSION, "dependencies": locked}
    _write_json(root / LOCK_NAME, lock)
    return lock


def check(root: Path) -> None:
    _check(root.resolve(), [])


def _check(
    root: Path,
    package_stack: list[str],
    expected_dependencies: dict[str, Any] | None = None,
) -> None:
    manifest = read_manifest(root)
    package_name = manifest["name"]
    if package_name in package_stack:
        cycle = " -> ".join((*package_stack, package_name))
        raise PackageError(f"Dependency cycle detected: {cycle}.")
    package_stack = [*package_stack, package_name]
    lock = read_lockfile(root)
    manifest_dependencies = manifest["dependencies"]
    locked_dependencies = lock["dependencies"]
    if (
        expected_dependencies is not None
        and locked_dependencies != expected_dependencies
    ):
        raise PackageError(
            f"Dependency graph for package '{package_name}' differs from the "
            "root lockfile; run 'YubaLANG package install'."
        )
    if set(manifest_dependencies) != set(locked_dependencies):
        raise PackageError(
            "Manifest dependencies do not match the lockfile; run "
            "'YubaLANG package install'."
        )
    for name, source in manifest_dependencies.items():
        entry = locked_dependencies.get(name)
        if not isinstance(entry, dict) or entry.get("source") != source:
            raise PackageError(
                f"Dependency '{name}' differs from the lockfile; "
                "run 'YubaLANG package install'."
            )
        package = entry.get("package")
        if not isinstance(package, dict):
            raise PackageError(
                f"Lockfile entry for '{name}' has no package identity; "
                "run 'YubaLANG package install'."
            )
        nested_dependencies = entry.get("dependencies")
        if not isinstance(nested_dependencies, dict):
            raise PackageError(
                f"Lockfile entry for '{name}' has no locked dependency graph; "
                "run 'YubaLANG package install'."
            )
        resolved = entry.get("resolved")
        if not isinstance(resolved, dict):
            raise PackageError(f"Lockfile entry for '{name}' is malformed.")
        if "path" in source:
            expected_path = Path(source["path"]).as_posix()
            if resolved.get("path") != expected_path:
                raise PackageError(f"Lockfile path for dependency '{name}' is inconsistent.")
            dependency_root = (root / resolved["path"]).resolve()
            if not dependency_root.is_dir():
                raise PackageError(f"Path dependency '{name}' is missing: {dependency_root}")
        else:
            if (
                not isinstance(resolved.get("rev"), str)
                or not _COMMIT_ID.fullmatch(resolved["rev"])
            ):
                raise PackageError(f"Lockfile entry for '{name}' has no Git revision.")
            dependency_root = root / PACKAGE_CACHE / name
            if not (dependency_root / ".git").is_dir():
                raise PackageError(
                    f"Git dependency '{name}' is not installed; run "
                    "'YubaLANG package install'."
                )
            revision = _git(dependency_root, "rev-parse", "HEAD")
            if revision != resolved["rev"]:
                raise PackageError(
                    f"Installed Git dependency '{name}' is at {revision}, "
                    f"not locked revision {resolved['rev']}."
                )
            origin = _git(dependency_root, "remote", "get-url", "origin")
            if origin != source["git"]:
                raise PackageError(
                    f"Installed Git dependency '{name}' has origin '{origin}', "
                    f"not '{source['git']}'."
                )
            status = _git(
                dependency_root,
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--",
                ".",
                ":!.yuba",
            )
            changes = [
                line
                for line in status.splitlines()
                if not (line.startswith("?? ") and line[3:] == LOCK_NAME)
            ]
            if changes:
                raise PackageError(
                    f"Installed Git dependency '{name}' has modified files; "
                    "run 'YubaLANG package install' to restore the locked revision."
                )
        dependency_manifest = read_manifest(dependency_root)
        if dependency_manifest["name"] != name:
            raise PackageError(
                f"Dependency '{name}' points to package "
                f"'{dependency_manifest['name']}' at {dependency_root}."
            )
        expected_package = {
            field: dependency_manifest[field]
            for field in ("name", "version", "entry", "yubalang")
        }
        if package != expected_package:
            raise PackageError(
                f"Package '{name}' metadata differs from the lockfile; "
                "run 'YubaLANG package install'."
            )
        resolve_entry(dependency_root, dependency_manifest)
        _check(dependency_root, package_stack, nested_dependencies)


def _parse_add(args: list[str]) -> tuple[str, dict[str, str]]:
    if len(args) < 3:
        raise PackageError(
            "Usage: YubaLANG package add <name> --path <directory> | "
            "--git <url> [--rev <revision>]"
        )
    name = args[0]
    _validate_name(name)
    source_option = args[1]
    if source_option == "--path" and len(args) == 3:
        return name, {"path": args[2]}
    if source_option == "--git" and len(args) in (3, 5):
        source = {"git": args[2]}
        if len(args) == 3:
            return name, source
        if args[3] == "--rev":
            source["rev"] = args[4]
        else:
            raise PackageError(
                "Usage: YubaLANG package add <name> --git <url> [--rev <revision>]"
            )
        return name, source
    raise PackageError(
        "Usage: YubaLANG package add <name> --path <directory> | "
        "--git <url> [--rev <revision>]"
    )


def run_package_command(arguments: list[str]) -> int:
    if not arguments:
        print(
            "Usage: YubaLANG package <init|add|remove|install|update|list|check> "
            "[arguments]",
            file=sys.stderr,
        )
        return 2
    command, args = arguments[0], arguments[1:]
    try:
        if command == "init":
            if len(args) > 1:
                raise PackageError("Usage: YubaLANG package init [directory]")
            root = Path(args[0] if args else ".").resolve()
            try:
                root.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                raise PackageError(f"Cannot create project directory '{root}': {error}") from error
            manifest_path = root / MANIFEST_NAME
            if manifest_path.exists():
                raise PackageError(f"Manifest already exists: {manifest_path}")
            name = re.sub(r"[^A-Za-z0-9_-]", "-", root.name) or "project"
            if not name[0].isalpha():
                name = f"project-{name}"
            _write_json(
                manifest_path,
                {
                    "name": name,
                    "version": "0.1.0",
                    "entry": "main.yl",
                    "yubalang": SUPPORTED_YUBALANG,
                    "dependencies": {},
                },
            )
            entry = root / "main.yl"
            if not entry.exists():
                try:
                    entry.write_text(
                        'text output "Hello from YubaLANG!"\n', encoding="utf-8"
                    )
                except OSError as error:
                    manifest_path.unlink(missing_ok=True)
                    raise PackageError(f"Cannot create entry file '{entry}': {error}") from error
            print(f"Created YubaLANG project at {root}")
            return 0

        root = find_project_root(Path.cwd())
        if root is None:
            raise PackageError(
                f"No {MANIFEST_NAME} found in this directory or its parents; "
                "run 'YubaLANG package init'."
            )

        if command == "add":
            name, source = _parse_add(args)
            manifest = read_manifest(root)
            previous_manifest = (root / MANIFEST_NAME).read_text(encoding="utf-8")
            manifest["dependencies"][name] = source
            _write_json(root / MANIFEST_NAME, manifest)
            try:
                install(root)
            except PackageError:
                (root / MANIFEST_NAME).write_text(previous_manifest, encoding="utf-8")
                raise
            print(f"Added dependency '{name}'.")
        elif command == "remove":
            if len(args) != 1:
                raise PackageError("Usage: YubaLANG package remove <name>")
            manifest = read_manifest(root)
            if args[0] not in manifest["dependencies"]:
                raise PackageError(f"Dependency '{args[0]}' is not in the manifest.")
            previous_manifest = (root / MANIFEST_NAME).read_text(encoding="utf-8")
            del manifest["dependencies"][args[0]]
            _write_json(root / MANIFEST_NAME, manifest)
            try:
                install(root)
            except PackageError:
                (root / MANIFEST_NAME).write_text(previous_manifest, encoding="utf-8")
                raise
            print(f"Removed dependency '{args[0]}'.")
        elif command == "install":
            if args:
                raise PackageError("Usage: YubaLANG package install")
            install(root)
            print("Dependencies installed and lockfile updated.")
        elif command == "update":
            if len(args) > 1:
                raise PackageError("Usage: YubaLANG package update [name]")
            manifest = read_manifest(root)
            if args and args[0] not in manifest["dependencies"]:
                raise PackageError(f"Dependency '{args[0]}' is not in the manifest.")
            install(root, update={args[0]} if args else True)
            print("Dependencies updated.")
        elif command == "list":
            if args:
                raise PackageError("Usage: YubaLANG package list")
            manifest = read_manifest(root)
            for name in sorted(manifest["dependencies"]):
                source = manifest["dependencies"][name]
                detail = source.get("path", source.get("git", ""))
                print(f"{name}: {detail}")
        elif command == "check":
            if args:
                raise PackageError("Usage: YubaLANG package check")
            check(root)
            print("Manifest, lockfile, and installed dependencies are consistent.")
        else:
            raise PackageError(f"Unknown package command: {command}")
    except PackageError as error:
        print(f"package: {error}", file=sys.stderr)
        return 1
    return 0


def resolve_dependency(root: Path, name: str) -> Path | None:
    manifest = read_manifest(root)
    if name not in manifest["dependencies"]:
        return None
    check(root)
    entry = read_lockfile(root)["dependencies"][name]
    resolved = entry["resolved"]
    if "path" in resolved:
        return (root / resolved["path"]).resolve()
    return (root / PACKAGE_CACHE / name).resolve()


def resolve_entry(root: Path, manifest: dict[str, Any]) -> Path:
    entry = Path(manifest["entry"])
    package_root = root.resolve()
    resolved = (package_root / entry).resolve()
    if entry.is_absolute() or package_root not in resolved.parents:
        raise PackageError(
            f"Package entry '{manifest['entry']}' must stay inside {package_root}."
        )
    if not resolved.is_file():
        raise PackageError(f"Package entry file does not exist: {resolved}")
    return resolved
