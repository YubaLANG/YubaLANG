# YubaLANG Executable
# Copyleft 🄯 2026 YubaLANG Tecnhologies\

import sys
from pathlib import Path

from lang.formatter import FormatError, format_source
from lang.interpreter import run_file
from lang.lsp import serve


def _format_paths(paths: list[str], check: bool) -> int:
    files: list[Path] = []
    for value in paths:
        path = Path(value)
        if path.is_dir():
            files.extend(
                candidate for candidate in path.rglob("*.hl")
                if not any(part.startswith(".") for part in candidate.relative_to(path).parts[:-1])
            )
        elif path.is_file() and path.suffix == ".hl":
            files.append(path)
        else:
            print(f"fmt: not a .hl file or directory: {path}", file=sys.stderr)
            return 1

    files = sorted(set(files))
    if not files:
        print("fmt: no .hl files found", file=sys.stderr)
        return 1

    changed = False
    for path in files:
        try:
            with path.open("r", encoding="utf-8", newline="") as source_file:
                source = source_file.read()
            formatted = format_source(source)
        except (OSError, UnicodeError, FormatError) as error:
            print(f"fmt: {path}: {error}", file=sys.stderr)
            return 1

        if source != formatted:
            changed = True
            if check:
                print(f"Would reformat {path}")
            else:
                try:
                    with path.open("w", encoding="utf-8", newline="\n") as output_file:
                        output_file.write(formatted)
                except (OSError, UnicodeError) as error:
                    print(f"fmt: {path}: {error}", file=sys.stderr)
                    return 1
                print(f"Formatted {path}")

    if check and changed:
        return 1
    if not changed:
        print("All files are formatted.")
    return 0


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--lsp":
        serve()
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "fmt":
        arguments = sys.argv[2:]
        check = False
        if arguments and arguments[0] in ("--check", "--write"):
            check = arguments.pop(0) == "--check"
        if not arguments:
            print("Usage: py YubaLANG.py fmt [--check|--write] <file.hl|directory>...", file=sys.stderr)
            sys.exit(2)
        sys.exit(_format_paths(arguments, check))

    if len(sys.argv) != 2:
        print("Usage: py YubaLANG.py <file.hl> | --lsp | fmt [--check|--write] <file.hl|directory>...")
        sys.exit(1)

    filename = sys.argv[1]

    run_file(filename)


if __name__ == "__main__":
    main()