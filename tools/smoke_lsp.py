import argparse
import json
from pathlib import Path
import subprocess


def _frame(message: dict[str, object]) -> bytes:
    content = json.dumps(message, separators=(",", ":")).encode("utf-8")
    return f"Content-Length: {len(content)}\r\n\r\n".encode("ascii") + content


def _read_frame(stream: bytes) -> dict[str, object]:
    header, separator, content = stream.partition(b"\r\n\r\n")
    if not separator:
        raise ValueError("LSP process did not emit a complete message header.")
    headers = {}
    for line in header.split(b"\r\n"):
        key, colon, value = line.partition(b":")
        if not colon:
            raise ValueError("LSP process emitted a malformed message header.")
        headers[key.decode("ascii").strip().lower()] = value.decode("ascii").strip()
    try:
        length = int(headers["content-length"])
    except (KeyError, ValueError) as error:
        raise ValueError("LSP process did not emit a valid Content-Length.") from error
    if len(content) != length:
        raise ValueError("LSP process emitted an incomplete message.")
    message = json.loads(content.decode("utf-8"))
    if not isinstance(message, dict):
        raise ValueError("LSP response must be a JSON object.")
    return message


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test a YubaLANG LSP executable.")
    parser.add_argument("executable", type=Path)
    arguments = parser.parse_args()
    incoming = (
        _frame({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"capabilities": {}},
        })
        + _frame({"jsonrpc": "2.0", "method": "exit"})
    )
    process = subprocess.run(
        [str(arguments.executable), "--lsp"],
        input=incoming,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise SystemExit(
            f"LSP executable exited with {process.returncode}: "
            f"{process.stderr.decode('utf-8', errors='replace')}"
        )
    response = _read_frame(process.stdout)
    if response.get("id") != 1 or "result" not in response:
        raise SystemExit(f"LSP executable returned an invalid initialize response: {response}")
    capabilities = response["result"].get("capabilities")
    if not isinstance(capabilities, dict) or not capabilities.get("definitionProvider"):
        raise SystemExit("LSP initialize response is missing advertised capabilities.")
    print("LSP initialize smoke test passed.")


if __name__ == "__main__":
    main()
