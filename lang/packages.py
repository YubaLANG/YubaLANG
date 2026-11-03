"""Project manifests, dependency locking, and package-manager commands."""

import hashlib
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any


MANIFEST_NAME = "yuba.json"
LOCK_NAME = "yuba.lock.json"
LOCK_VERSION = 2
REGISTRY_LOCK_VERSION = 3
SUPPORTED_LOCK_VERSIONS = frozenset({1, LOCK_VERSION, REGISTRY_LOCK_VERSION})
SUPPORTED_YUBALANG = "1.3"
COMPATIBLE_YUBALANG_VERSIONS = {"1.2", SUPPORTED_YUBALANG}
PACKAGE_CACHE = Path(".yuba") / "packages"
_PACKAGE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
_COMMIT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


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
    portable_names: set[str] = set()
    for name, source in dependencies.items():
        _validate_name(name)
        if name.casefold() in portable_names:
            raise PackageError(
                f"Manifest '{path}' contains dependency names that collide "
                "on case-insensitive filesystems."
            )
        portable_names.add(name.casefold())
        _validate_source(name, source)
    return data


def _validate_name(name: str) -> None:
    if (
        not isinstance(name, str)
        or not _PACKAGE_NAME.fullmatch(name)
        or name.casefold() in _WINDOWS_RESERVED_NAMES
    ):
        raise PackageError(
            f"Invalid package name '{name}'; use a letter followed by letters, "
            "digits, underscores, or hyphens, excluding reserved Windows names."
        )


def _validate_source(name: str, source: Any) -> None:
    if not isinstance(source, dict) or len(source) not in (1, 2):
        raise PackageError(
            f"Dependency '{name}' must specify a path, Git, or registry source."
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
    elif set(source) == {"registry"}:
        _validate_version_requirement(name, source["registry"])
    else:
        raise PackageError(
            f"Dependency '{name}' must specify a 'path', 'git', or 'registry' source."
        )


_SEMVER_PATTERN = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\Z"
)


def _parse_semver(value: Any) -> tuple[int, int, int, tuple[int | str, ...]]:
    if not isinstance(value, str):
        raise ValueError(f"Invalid semantic version: {value!r}")
    match = _SEMVER_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(f"Invalid semantic version '{value}'.")
    prerelease: list[int | str] = []
    for identifier in (match.group(4) or "").split(".") if match.group(4) else ():
        if identifier.isdigit():
            if len(identifier) > 1 and identifier.startswith("0"):
                raise ValueError(f"Invalid semantic version '{value}'.")
            prerelease.append(int(identifier))
        else:
            prerelease.append(identifier)
    return (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
        tuple(prerelease),
    )


def _compare_semver(
    left: tuple[int, int, int, tuple[int | str, ...]],
    right: tuple[int, int, int, tuple[int | str, ...]],
) -> int:
    if left[:3] != right[:3]:
        return (left[:3] > right[:3]) - (left[:3] < right[:3])
    left_pre, right_pre = left[3], right[3]
    if not left_pre or not right_pre:
        if not left_pre and right_pre:
            return 1
        if left_pre and not right_pre:
            return -1
        return 0
    for a, b in zip(left_pre, right_pre):
        if a == b:
            continue
        if isinstance(a, int) != isinstance(b, int):
            return -1 if isinstance(a, int) else 1
        return (a > b) - (a < b)
    return (len(left_pre) > len(right_pre)) - (len(left_pre) < len(right_pre))


def _validate_version_requirement(name: str, requirement: Any) -> None:
    if not isinstance(requirement, str) or not requirement.strip():
        raise PackageError(f"Dependency '{name}' has an invalid registry version requirement.")
    for token in re.split(r"[\s,]+", requirement.strip()):
        if token in ("*", "x", "X"):
            continue
        match = re.fullmatch(r"(>=|<=|>|<|=|\^|~)?(.+)", token)
        if match is None:
            raise PackageError(f"Dependency '{name}' has an invalid version requirement.")
        raw = match.group(2)
        if any(part.casefold() in ("x", "*") for part in raw.split(".")):
            parts = raw.split(".")
            wildcard = next(
                (index for index, part in enumerate(parts) if part.casefold() in ("x", "*")),
                None,
            )
            if (
                wildcard is None
                or wildcard == 0 and len(parts) != 1
                or any(part.casefold() not in ("x", "*") for part in parts[wildcard:])
                or any(not part.isdigit() or part.startswith("0") and len(part) > 1
                       for part in parts[:wildcard])
                or len(parts) > 3
            ):
                raise PackageError(f"Dependency '{name}' has an invalid version requirement.")
        else:
            try:
                _parse_semver(raw)
            except ValueError as error:
                raise PackageError(
                    f"Dependency '{name}' has an invalid version requirement: {error}"
                ) from error


def _satisfies_requirement(version_text: str, requirement: str) -> bool:
    version = _parse_semver(version_text)
    tokens = re.split(r"[\s,]+", requirement.strip())
    allows_prerelease = False
    for token in tokens:
        match = re.fullmatch(r"(?:>=|<=|>|<|=|\^|~)?(.+)", token)
        if match is None:
            continue
        raw = match.group(1)
        if any(part.casefold() in ("x", "*") for part in raw.split(".")):
            continue
        target = _parse_semver(raw)
        if target[3] and version[:3] == target[:3]:
            allows_prerelease = True
            break
    if version[3] and not allows_prerelease:
        return False
    for token in tokens:
        if token in ("*", "x", "X"):
            continue
        match = re.fullmatch(r"(>=|<=|>|<|=|\^|~)?(.+)", token)
        if match is None:
            return False
        operator, raw = match.group(1) or "=", match.group(2)
        if any(part.casefold() in ("x", "*") for part in raw.split(".")):
            parts = raw.split(".")
            index = next(
                i for i, part in enumerate(parts) if part.casefold() in ("x", "*")
            )
            if index == 0:
                continue
            lower_parts = [int(part) for part in parts[:index]]
            lower = tuple(lower_parts + [0] * (3 - index)) + ((),)
            if index == 1:
                upper = (lower[0] + 1, 0, 0, ())
            elif index == 2:
                upper = (lower[0], lower[1] + 1, 0, ())
            else:
                upper = (lower[0], lower[1], lower[2] + 1, ())
            if _compare_semver(version, lower) < 0 or _compare_semver(version, upper) >= 0:
                return False
            continue
        target = _parse_semver(raw)
        comparison = _compare_semver(version, target)
        if operator == "=" and comparison != 0:
            return False
        if operator == ">" and comparison <= 0:
            return False
        if operator == ">=" and comparison < 0:
            return False
        if operator == "<" and comparison >= 0:
            return False
        if operator == "<=" and comparison > 0:
            return False
        if operator in ("^", "~"):
            if operator == "~":
                upper = (target[0], target[1] + 1, 0, ())
            elif target[0]:
                upper = (target[0] + 1, 0, 0, ())
            elif target[1]:
                upper = (0, target[1] + 1, 0, ())
            else:
                upper = (0, 0, target[2] + 1, ())
            if comparison < 0 or _compare_semver(version, upper) >= 0:
                return False
    return True


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
        or not isinstance(data.get("lock_version"), int)
        or isinstance(data.get("lock_version"), bool)
        or data.get("lock_version") not in SUPPORTED_LOCK_VERSIONS
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise PackageError(f"Cannot read cached registry artifact '{path}': {error}") from error
    return digest.hexdigest()


def _registry_tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    files = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ".yuba" in relative.parts or ".git" in relative.parts:
            continue
        if path.is_symlink():
            raise PackageError(f"Registry package contains a symbolic link: {path}")
        if path.is_file() and path.name != LOCK_NAME:
            files.append(path)
        elif not path.is_dir() and not path.is_file():
            raise PackageError(f"Registry package contains an unsupported file: {path}")
    files.sort(
        key=lambda path: path.relative_to(root).as_posix().encode("utf-8")
    )
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        try:
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as error:
            raise PackageError(f"Cannot read registry package file '{path}': {error}") from error
    return digest.hexdigest()


def _check_registry_dependency(
    root: Path,
    name: str,
    source: dict[str, Any],
    resolved: dict[str, Any],
) -> Path:
    endpoint = resolved.get("registry")
    artifact = resolved.get("artifact")
    version = resolved.get("version")
    artifact_digest = resolved.get("sha256")
    tree_digest = resolved.get("tree_sha256")
    if (
        not isinstance(endpoint, str)
        or not isinstance(artifact, str)
        or not isinstance(version, str)
        or not isinstance(artifact_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", artifact_digest)
        or not isinstance(tree_digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", tree_digest)
    ):
        raise PackageError(f"Registry lock entry for '{name}' has invalid identity.")
    try:
        parsed_endpoint = urllib.parse.urlsplit(endpoint)
        parsed_endpoint.port
    except ValueError as error:
        raise PackageError(f"Registry URL for '{name}' is invalid: {error}") from error
    if (
        parsed_endpoint.scheme not in ("https", "http")
        or not parsed_endpoint.hostname
        or parsed_endpoint.username is not None
        or parsed_endpoint.password is not None
        or parsed_endpoint.query
        or parsed_endpoint.fragment
        or (
            parsed_endpoint.scheme != "https"
            and parsed_endpoint.hostname not in ("localhost", "127.0.0.1", "::1")
        )
    ):
        raise PackageError(f"Registry URL for '{name}' is not a trusted HTTPS URL.")
    try:
        artifact_url = urllib.parse.urljoin(endpoint.rstrip("/") + "/", artifact)
        parsed_artifact = urllib.parse.urlsplit(artifact_url)
        parsed_artifact.port
    except ValueError as error:
        raise PackageError(f"Artifact URL for '{name}' is invalid: {error}") from error
    if (
        (parsed_artifact.scheme, parsed_artifact.hostname, parsed_artifact.port)
        != (parsed_endpoint.scheme, parsed_endpoint.hostname, parsed_endpoint.port)
        or parsed_artifact.username is not None
        or parsed_artifact.password is not None
        or parsed_artifact.query
        or parsed_artifact.fragment
    ):
        raise PackageError(f"Artifact URL for '{name}' is outside its trusted registry.")
    try:
        if not _satisfies_requirement(version, source["registry"]):
            raise PackageError(
                f"Locked version {version} of '{name}' does not satisfy "
                f"'{source['registry']}'."
            )
    except ValueError as error:
        raise PackageError(f"Registry lock version for '{name}' is invalid: {error}") from error
    archive = root / ".yuba" / "artifacts" / f"{artifact_digest}.tar.gz"
    if not archive.is_file():
        raise PackageError(
            f"Registry artifact for '{name}' is not cached; run "
            "'yubapkg package install'."
        )
    if _sha256_file(archive) != artifact_digest:
        raise PackageError(f"Cached registry artifact for '{name}' failed SHA-256 verification.")
    dependency_root = root / ".yuba" / "packages" / name
    if not dependency_root.is_dir() or _registry_tree_sha256(dependency_root) != tree_digest:
        raise PackageError(
            f"Installed registry package '{name}' was modified or is missing; "
            "run 'yubapkg package install'."
        )
    manifest = read_manifest(dependency_root)
    if manifest["name"] != name or manifest["version"] != version:
        raise PackageError(f"Installed registry package '{name}' has the wrong identity.")
    resolve_entry(dependency_root, manifest)
    return dependency_root


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

    if "registry" in source:
        raise PackageError(
            "Registry dependencies must be installed with "
            "'yubapkg package install'."
        )

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
    has_nested_graph = lock["lock_version"] in (
        LOCK_VERSION,
        REGISTRY_LOCK_VERSION,
    )
    manifest_dependencies = manifest["dependencies"]
    locked_dependencies = lock["dependencies"]
    if (
        has_nested_graph
        and expected_dependencies is not None
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
        if has_nested_graph:
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
        elif "registry" in source:
            if lock["lock_version"] != REGISTRY_LOCK_VERSION:
                raise PackageError(
                    "Registry dependencies require lockfile format 3; run "
                    "'yubapkg package install'."
                )
            dependency_root = _check_registry_dependency(
                root, name, source, resolved
            )
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
        resolve_entry(dependency_root, dependency_manifest)
        if has_nested_graph:
            expected_package = {
                field: dependency_manifest[field]
                for field in ("name", "version", "entry", "yubalang")
            }
            if package != expected_package:
                raise PackageError(
                    f"Package '{name}' metadata differs from the lockfile; "
                    "run 'YubaLANG package install'."
                )
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
                detail = source.get(
                    "path", source.get("git", source.get("registry", ""))
                )
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
    if "registry" in resolved:
        return (root / ".yuba" / "packages" / name).resolve()
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
