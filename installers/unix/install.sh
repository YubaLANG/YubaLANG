#!/bin/sh
set -eu

REPOSITORY="yubalang/yubalang"
INSTALL_DIR="${YUBALANG_INSTALL_DIR:-$HOME/.local/bin}"
VERSION="latest"
UNINSTALL=0

usage() {
    printf 'Usage: install.sh [--version v1.2.0] [--uninstall]\n' >&2
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --version)
            if [ "$#" -lt 2 ]; then
                usage
                exit 2
            fi
            VERSION=$2
            shift 2
            ;;
        --uninstall)
            UNINSTALL=1
            shift
            ;;
        *)
            usage
            exit 2
            ;;
    esac
done

if [ "$UNINSTALL" -eq 1 ]; then
    rm -f "$INSTALL_DIR/YubaLANG"
    printf 'Removed %s\n' "$INSTALL_DIR/YubaLANG"
    exit 0
fi

case "$VERSION" in
    latest|v[0-9]*) ;;
    *)
        printf 'install: version must be "latest" or a version tag such as v1.2.0\n' >&2
        exit 2
        ;;
esac
case "$VERSION" in
    *[!A-Za-z0-9._-]*)
        printf 'install: invalid version tag: %s\n' "$VERSION" >&2
        exit 2
        ;;
esac

OS=$(uname -s)
ARCH=$(uname -m)
case "$OS:$ARCH" in
    Linux:x86_64|Linux:amd64)
        ASSET="YubaLANG-linux-x64.tar.gz"
        ;;
    Darwin:x86_64)
        ASSET="YubaLANG-macos-x64.tar.gz"
        ;;
    Darwin:arm64|Darwin:aarch64)
        ASSET="YubaLANG-macos-arm64.tar.gz"
        ;;
    *)
        printf 'install: unsupported platform: %s %s\n' "$OS" "$ARCH" >&2
        exit 1
        ;;
esac

if ! command -v curl >/dev/null 2>&1 || ! command -v tar >/dev/null 2>&1; then
    printf 'install: curl and tar are required\n' >&2
    exit 1
fi

if [ "$VERSION" = "latest" ]; then
    RELEASE_URL="https://github.com/$REPOSITORY/releases/latest/download"
else
    RELEASE_URL="https://github.com/$REPOSITORY/releases/download/$VERSION"
fi

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT
trap 'exit 1' HUP INT TERM
curl --fail --location --silent --show-error "$RELEASE_URL/$ASSET" -o "$TEMP_DIR/$ASSET"
curl --fail --location --silent --show-error "$RELEASE_URL/SHA256SUMS" -o "$TEMP_DIR/SHA256SUMS"

EXPECTED_HASH=$(awk -v asset="$ASSET" '$2 == asset || $2 == "*" asset { print $1; exit }' "$TEMP_DIR/SHA256SUMS")
if [ -z "$EXPECTED_HASH" ]; then
    printf 'install: checksum for %s was not found in the release\n' "$ASSET" >&2
    exit 1
fi
if command -v sha256sum >/dev/null 2>&1; then
    ACTUAL_HASH=$(sha256sum "$TEMP_DIR/$ASSET" | awk '{ print $1 }')
elif command -v shasum >/dev/null 2>&1; then
    ACTUAL_HASH=$(shasum -a 256 "$TEMP_DIR/$ASSET" | awk '{ print $1 }')
else
    printf 'install: sha256sum or shasum is required to verify the download\n' >&2
    exit 1
fi
if [ "$EXPECTED_HASH" != "$ACTUAL_HASH" ]; then
    printf 'install: checksum verification failed for %s\n' "$ASSET" >&2
    exit 1
fi

tar -xzf "$TEMP_DIR/$ASSET" -C "$TEMP_DIR"
if [ ! -f "$TEMP_DIR/YubaLANG" ]; then
    printf 'install: release archive does not contain YubaLANG\n' >&2
    exit 1
fi
mkdir -p "$INSTALL_DIR"
install -m 755 "$TEMP_DIR/YubaLANG" "$INSTALL_DIR/YubaLANG"
printf 'Installed YubaLANG to %s\n' "$INSTALL_DIR/YubaLANG"
case ":$PATH:" in
    *":$INSTALL_DIR:"*) ;;
    *)
        printf 'Add this directory to your PATH to run YubaLANG from any folder:\n  %s\n' "$INSTALL_DIR"
        ;;
esac
