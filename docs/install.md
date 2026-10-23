# Installing YubaLANG

YubaLANG releases include standalone executables for Windows x64, Linux x64,
macOS Intel, and macOS Apple Silicon. They bundle the Python runtime; users do
not need to install Python. Linux builds target Ubuntu 22.04 (glibc 2.35) or
newer. macOS builds target macOS 13 or newer.

## Install or update

On macOS or Linux, run:

```sh
curl -fsSL https://raw.githubusercontent.com/yubalang/yubalang/main/installers/unix/install.sh | sh
```

On Windows, run in PowerShell:

```powershell
irm https://raw.githubusercontent.com/yubalang/yubalang/main/installers/windows/install.ps1 | iex
```

The installers download the latest GitHub release, verify the SHA-256 checksum,
and install or replace the executable. To install a specific tag, download the
corresponding installer script and pass `--version v1.2.0` on macOS/Linux or
`-Version v1.2.0` on Windows. Re-running the installer updates an existing
installation.

The Unix installer installs to `~/.local/bin` by default. If that directory is
not already on `PATH`, add it to your shell's PATH. Set `YUBALANG_INSTALL_DIR`
to use a different directory. The Windows installer installs to
`%LOCALAPPDATA%\Programs\YubaLANG` and adds that directory to the current user's
PATH; open a new terminal after installation.

To uninstall, run the Unix script with `--uninstall`, or run the Windows script
with `-Uninstall`. The Windows installer removes its PATH entry as well.

## First run

```text
YubaLANG.exe path\to\program.yl
YubaLANG fmt --check .
YubaLANG test
YubaLANG package init
```

On macOS and Linux, the executable is named `YubaLANG` (without `.exe`).
The test command discovers `*.yl` files in `tests/cases` by default; each test
needs a sibling `<name>.expected.txt` file containing its exact expected
standard output. Output comparison is the assertion mechanism; there is no
in-language assertion API yet. Tests are non-interactive and do not provide
setup/teardown hooks.

Projects can be initialized and dependencies managed with `YubaLANG package`.
See the [project and package guide](package-manager.md) for manifests,
lockfiles, imports, and path/Git dependencies.

## Unsigned releases

Release executables are not code-signed or notarized, avoiding the need for
signing certificates. Windows SmartScreen or macOS Gatekeeper may warn when
running a downloaded executable. If you choose to run a release you trust,
Windows may offer a "More info" then "Run anyway" option; macOS may allow
"Open" from the Finder Control-click menu. The release SHA-256 file detects
accidental corruption but is not a digital signature. Review the release and
its checksum before proceeding; do not disable operating-system security
checks globally.

## Build pipeline

Push a version tag such as `v1.2.0` to build and publish the four platform
archives. The workflow runs the test suite on each build platform, bundles
Python with PyInstaller, and attaches SHA-256 checksums to the GitHub release.
Builds run on GitHub-hosted Windows, Ubuntu 22.04, macOS Intel, and Apple
Silicon runners.
