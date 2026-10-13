# YubaLANG Executable
# Copyleft 🄯 2026 YubaLANG Tecnhologies\

import sys

from lang.interpreter import run_file
from lang.lsp import serve


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--lsp":
        serve()
        return

    if len(sys.argv) != 2:
        print("Usage: py YubaLANG.py <file.hl> | --lsp")
        sys.exit(1)

    filename = sys.argv[1]

    run_file(filename)


if __name__ == "__main__":
    main()