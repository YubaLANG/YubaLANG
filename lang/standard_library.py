"""Bundled standard-library modules exposed through the language importer."""

import base64
import binascii
import csv
import datetime as datetime_module
import hashlib
import io
import json
import math
import os
import random
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


STANDARD_MODULES = frozenset(
    {
        "std.path",
        "std.fs",
        "std.time",
        "std.random",
        "std.math",
        "std.json",
        "std.encoding",
        "std.process",
        "std.http",
        "std.csv",
        "std.url",
        "std.hash",
    }
)


def is_standard_module(name: str) -> bool:
    return name in STANDARD_MODULES


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string.")
    return value


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number.")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite.")
    return result


def _number(value: Any, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a number.")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{label} must be finite.")
    return value


def _positive_integer(value: Any, label: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer.")
    if not 1 <= value <= maximum:
        raise ValueError(f"{label} must be between 1 and {maximum}.")
    return value


def _path_functions() -> dict[str, Callable[..., Any]]:
    def join(*parts: str) -> str:
        if not parts:
            raise TypeError("join() requires at least one path.")
        return str(Path(_string(parts[0], "Path")).joinpath(
            *(_string(part, "Path") for part in parts[1:])
        ))

    def normalize(path: str) -> str:
        return os.path.normpath(_string(path, "Path"))

    def basename(path: str) -> str:
        return Path(_string(path, "Path")).name

    def dirname(path: str) -> str:
        return str(Path(_string(path, "Path")).parent)

    def extension(path: str) -> str:
        return Path(_string(path, "Path")).suffix

    def is_absolute(path: str) -> bool:
        return Path(_string(path, "Path")).is_absolute()

    def resolve(path: str) -> str:
        return str(Path(_string(path, "Path")).resolve())

    def relative(path: str, base: str) -> str:
        return os.path.relpath(
            _string(path, "Path"), _string(base, "Base path")
        )

    return {
        "join": join,
        "normalize": normalize,
        "basename": basename,
        "dirname": dirname,
        "extension": extension,
        "is_absolute": is_absolute,
        "resolve": resolve,
        "relative": relative,
    }


def _filesystem_functions() -> dict[str, Callable[..., Any]]:
    def read_text(path: str) -> str:
        return Path(_string(path, "Path")).read_text(encoding="utf-8")

    def write_data(target: Path, data: bytes, overwrite: bool) -> None:
        if not isinstance(overwrite, bool):
            raise TypeError("overwrite must be a boolean.")
        if not overwrite:
            descriptor = os.open(
                target,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                0o666,
            )
            try:
                with os.fdopen(descriptor, "wb") as output:
                    output.write(data)
            except BaseException:
                target.unlink(missing_ok=True)
                raise
            return None

        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=target.parent, delete=False
            ) as output:
                temporary_path = output.name
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, target)
            temporary_path = None
        finally:
            if temporary_path is not None:
                Path(temporary_path).unlink(missing_ok=True)
        return None

    def read_bytes(path: str) -> bytes:
        return Path(_string(path, "Path")).read_bytes()

    def write_text(path: str, contents: str, overwrite: bool = False) -> None:
        target = Path(_string(path, "Path"))
        data = _string(contents, "Contents").encode("utf-8")
        return write_data(target, data, overwrite)

    def write_bytes(
        path: str,
        contents: bytes | bytearray,
        overwrite: bool = False,
    ) -> None:
        if not isinstance(contents, (bytes, bytearray)):
            raise TypeError("Contents must be bytes or bytearray.")
        return write_data(
            Path(_string(path, "Path")),
            bytes(contents),
            overwrite,
        )

    def exists(path: str) -> bool:
        return Path(_string(path, "Path")).exists()

    def is_file(path: str) -> bool:
        return Path(_string(path, "Path")).is_file()

    def list_dir(path: str) -> list[str]:
        return sorted(
            item.name for item in Path(_string(path, "Path")).iterdir()
        )

    def mkdir(path: str, parents: bool = False, exist_ok: bool = False) -> None:
        if not isinstance(parents, bool) or not isinstance(exist_ok, bool):
            raise TypeError("parents and exist_ok must be booleans.")
        Path(_string(path, "Path")).mkdir(
            parents=parents, exist_ok=exist_ok
        )
        return None

    def remove_file(path: str) -> None:
        Path(_string(path, "Path")).unlink()
        return None

    return {
        "read_text": read_text,
        "write_text": write_text,
        "read_bytes": read_bytes,
        "write_bytes": write_bytes,
        "exists": exists,
        "is_file": is_file,
        "list_dir": list_dir,
        "mkdir": mkdir,
        "remove_file": remove_file,
    }


def _time_functions(clock: Callable[[], float]) -> dict[str, Callable[..., Any]]:
    def now() -> float:
        return clock()

    def utc_iso(timestamp: int | float) -> str:
        moment = datetime_module.datetime.fromtimestamp(
            _finite_number(timestamp, "Timestamp"),
            tz=datetime_module.timezone.utc,
        )
        return moment.isoformat().replace("+00:00", "Z")

    def parse_iso(value: str) -> float:
        text = _string(value, "ISO timestamp")
        if not text.endswith("Z") and "+" not in text[10:] and "-" not in text[10:]:
            raise ValueError("ISO timestamp must include a UTC offset.")
        moment = datetime_module.datetime.fromisoformat(
            text[:-1] + "+00:00" if text.endswith("Z") else text
        )
        if moment.tzinfo is None:
            raise ValueError("ISO timestamp must include a UTC offset.")
        return moment.timestamp()

    def sleep(seconds: int | float) -> None:
        duration = _finite_number(seconds, "Duration")
        if duration < 0:
            raise ValueError("Duration must not be negative.")
        time.sleep(duration)
        return None

    return {"now": now, "utc_iso": utc_iso, "parse_iso": parse_iso, "sleep": sleep}


def _random_functions(source: random.Random) -> dict[str, Callable[..., Any]]:
    def seed(value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("Seed must be an integer.")
        source.seed(value)
        return None

    def integer(minimum: int, maximum: int) -> int:
        for value, label in ((minimum, "Minimum"), (maximum, "Maximum")):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{label} must be an integer.")
        if minimum > maximum:
            raise ValueError("Minimum must not exceed maximum.")
        return source.randint(minimum, maximum)

    def uniform(minimum: int | float, maximum: int | float) -> float:
        low = _finite_number(minimum, "Minimum")
        high = _finite_number(maximum, "Maximum")
        if low > high:
            raise ValueError("Minimum must not exceed maximum.")
        return source.uniform(low, high)

    def choice(values: list[Any]) -> Any:
        if not isinstance(values, (list, tuple, str)) or not values:
            raise ValueError("choice() requires a non-empty list, tuple, or string.")
        return source.choice(values)

    return {"seed": seed, "integer": integer, "uniform": uniform, "choice": choice}


def _math_functions() -> dict[str, Callable[..., Any]]:
    def numeric(function: Callable[[int | float], Any]) -> Callable[[Any], Any]:
        def apply(value: Any) -> Any:
            return function(_number(value, "Argument"))
        return apply

    def power(base: Any, exponent: Any) -> float:
        return math.pow(
            _number(base, "Base"),
            _number(exponent, "Exponent"),
        )

    def is_finite(value: Any) -> bool:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("Argument must be a number.")
        return math.isfinite(value)

    return {
        "abs": numeric(abs),
        "ceil": numeric(math.ceil),
        "floor": numeric(math.floor),
        "sqrt": numeric(math.sqrt),
        "pow": power,
        "sin": numeric(math.sin),
        "cos": numeric(math.cos),
        "is_finite": is_finite,
        "pi": lambda: math.pi,
        "e": lambda: math.e,
    }


def _json_functions() -> dict[str, Callable[..., Any]]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"Invalid JSON numeric constant '{value}'.")

    def loads(value: str) -> Any:
        return json.loads(
            _string(value, "JSON input"),
            parse_constant=reject_constant,
        )

    def dumps(value: Any, indent: int | None = None, sort_keys: bool = False) -> str:
        if indent is not None and (
            isinstance(indent, bool) or not isinstance(indent, int) or indent < 0
        ):
            raise ValueError("indent must be none or a non-negative integer.")
        if not isinstance(sort_keys, bool):
            raise TypeError("sort_keys must be a boolean.")
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=indent,
            sort_keys=sort_keys,
        )

    return {"loads": loads, "dumps": dumps}


def _encoding_functions() -> dict[str, Callable[..., Any]]:
    def utf8_encode(value: str) -> bytes:
        return _string(value, "Text").encode("utf-8")

    def utf8_decode(value: bytes | bytearray) -> str:
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError("UTF-8 input must be bytes or bytearray.")
        return bytes(value).decode("utf-8", errors="strict")

    def base64_encode(value: bytes | bytearray) -> str:
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError("Base64 input must be bytes or bytearray.")
        return base64.b64encode(bytes(value)).decode("ascii")

    def base64_decode(value: str) -> bytes:
        try:
            return base64.b64decode(
                _string(value, "Base64 input"), validate=True
            )
        except binascii.Error as error:
            raise ValueError(f"Invalid base64 input: {error}") from error

    return {
        "utf8_encode": utf8_encode,
        "utf8_decode": utf8_decode,
        "base64_encode": base64_encode,
        "base64_decode": base64_decode,
    }


def _csv_functions() -> dict[str, Callable[..., Any]]:
    def loads(value: str, delimiter: str = ",") -> list[list[str]]:
        text = _string(value, "CSV input")
        separator = _string(delimiter, "Delimiter")
        if len(separator) != 1 or separator in "\r\n":
            raise ValueError("CSV delimiter must be one non-newline character.")
        return [
            row
            for row in csv.reader(
                io.StringIO(text, newline=""),
                delimiter=separator,
                strict=True,
            )
        ]

    def dumps(rows: list[list[str]], delimiter: str = ",") -> str:
        separator = _string(delimiter, "Delimiter")
        if len(separator) != 1 or separator in "\r\n":
            raise ValueError("CSV delimiter must be one non-newline character.")
        if not isinstance(rows, (list, tuple)):
            raise TypeError("CSV rows must be a list or tuple of rows.")
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, delimiter=separator, lineterminator="\n")
        for row in rows:
            if not isinstance(row, (list, tuple)) or any(
                not isinstance(cell, str) for cell in row
            ):
                raise TypeError("Each CSV row must be a list or tuple of strings.")
            writer.writerow(row)
        return stream.getvalue()

    return {"loads": loads, "dumps": dumps}


def _url_functions() -> dict[str, Callable[..., Any]]:
    def parse(value: str) -> dict[str, Any]:
        parsed = urllib.parse.urlsplit(_string(value, "URL"))
        try:
            port = parsed.port
        except ValueError as error:
            raise ValueError(f"Invalid URL port: {error}") from error
        return {
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": port,
            "path": parsed.path,
            "query": parsed.query,
            "fragment": parsed.fragment,
            "username": parsed.username,
            "is_absolute": bool(parsed.scheme and parsed.netloc),
        }

    def join(base: str, reference: str) -> str:
        return urllib.parse.urljoin(
            _string(base, "Base URL"),
            _string(reference, "URL reference"),
        )

    def encode_component(value: str) -> str:
        return urllib.parse.quote(_string(value, "URL component"), safe="")

    def decode_component(value: str) -> str:
        try:
            return urllib.parse.unquote(
                _string(value, "URL component"),
                encoding="utf-8",
                errors="strict",
            )
        except UnicodeDecodeError as error:
            raise ValueError(f"URL component is not valid UTF-8: {error}") from error

    def parse_query(value: str) -> dict[str, list[str]]:
        pairs = urllib.parse.parse_qsl(
            _string(value, "Query string"),
            keep_blank_values=True,
            strict_parsing=False,
            encoding="utf-8",
            errors="strict",
        )
        result: dict[str, list[str]] = {}
        for key, item in pairs:
            result.setdefault(key, []).append(item)
        return result

    def build_query(values: dict[str, Any]) -> str:
        if not isinstance(values, dict):
            raise TypeError("Query parameters must be a dictionary.")
        normalized: dict[str, str | list[str]] = {}
        for key, value in values.items():
            if not isinstance(key, str):
                raise TypeError("Query parameter names must be strings.")
            if isinstance(value, str):
                normalized[key] = value
            elif isinstance(value, (list, tuple)) and all(
                isinstance(item, str) for item in value
            ):
                normalized[key] = list(value)
            else:
                raise TypeError(
                    "Query parameter values must be strings or lists of strings."
                )
        return urllib.parse.urlencode(normalized, doseq=True)

    return {
        "parse": parse,
        "join": join,
        "encode_component": encode_component,
        "decode_component": decode_component,
        "parse_query": parse_query,
        "build_query": build_query,
    }


def _hash_functions() -> dict[str, Callable[..., Any]]:
    def sha256(value: str | bytes | bytearray) -> str:
        if isinstance(value, str):
            data = value.encode("utf-8")
        elif isinstance(value, (bytes, bytearray)):
            data = bytes(value)
        else:
            raise TypeError("Hash input must be a string, bytes, or bytearray.")
        return hashlib.sha256(data).hexdigest()

    def sha256_file(path: str) -> str:
        digest = hashlib.sha256()
        try:
            with Path(_string(path, "Path")).open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as error:
            raise OSError(f"Cannot hash file '{path}': {error}") from error
        return digest.hexdigest()

    return {"sha256": sha256, "sha256_file": sha256_file}


def _process_functions(program_args: list[str]) -> dict[str, Callable[..., Any]]:
    def args() -> list[str]:
        return list(program_args)

    def env(name: str) -> str | None:
        return os.environ.get(_string(name, "Environment variable name"))

    def exit_process(code: int = 0) -> None:
        if isinstance(code, bool) or not isinstance(code, int):
            raise TypeError("Exit code must be an integer.")
        if not 0 <= code <= 255:
            raise ValueError("Exit code must be between 0 and 255.")
        raise SystemExit(code)

    def run(
        arguments: list[str],
        timeout: int | float = 30.0,
        max_output_bytes: int = 1_048_576,
    ) -> dict[str, Any]:
        if (
            not isinstance(arguments, list)
            or not arguments
            or any(not isinstance(item, str) for item in arguments)
        ):
            raise TypeError("Subprocess arguments must be a non-empty list of strings.")
        duration = _finite_number(timeout, "Timeout")
        if not 0 < duration <= 3600:
            raise ValueError("Timeout must be greater than 0 and at most 3600 seconds.")
        output_limit = _positive_integer(
            max_output_bytes, "Output limit", 67_108_864
        )
        if any("\x00" in item for item in arguments):
            raise ValueError("Subprocess arguments must not contain NUL characters.")

        process = subprocess.Popen(
            arguments,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        assert process.stdout is not None and process.stderr is not None
        output: dict[str, bytearray] = {
            "stdout": bytearray(),
            "stderr": bytearray(),
        }
        total_size = 0
        output_exceeded = False
        reader_errors: list[OSError] = []
        output_lock = threading.Lock()

        def capture(stream: Any, name: str) -> None:
            nonlocal total_size, output_exceeded
            try:
                while True:
                    chunk = stream.read(65536)
                    if not chunk:
                        return
                    with output_lock:
                        available = max(0, output_limit - total_size)
                        output[name].extend(chunk[:available])
                        total_size += min(len(chunk), available)
                        if len(chunk) > available:
                            output_exceeded = True
                            try:
                                process.kill()
                            except OSError:
                                pass
            except OSError as error:
                with output_lock:
                    reader_errors.append(error)
                try:
                    process.kill()
                except OSError:
                    pass

        readers = [
            threading.Thread(target=capture, args=(process.stdout, "stdout"), daemon=True),
            threading.Thread(target=capture, args=(process.stderr, "stderr"), daemon=True),
        ]
        for reader in readers:
            reader.start()
        try:
            return_code = process.wait(timeout=duration)
        except subprocess.TimeoutExpired as error:
            process.kill()
            process.wait()
            for reader in readers:
                reader.join()
            process.stdout.close()
            process.stderr.close()
            raise TimeoutError(f"Subprocess exceeded its {duration:g}-second timeout.") from error
        for reader in readers:
            reader.join()
        process.stdout.close()
        process.stderr.close()
        if reader_errors:
            raise OSError(f"Cannot capture subprocess output: {reader_errors[0]}") from reader_errors[0]
        if output_exceeded:
            raise ValueError(
                f"Subprocess output exceeded the {output_limit}-byte limit."
            )
        return {
            "exit_code": return_code,
            "stdout": bytes(output["stdout"]),
            "stderr": bytes(output["stderr"]),
        }

    return {"args": args, "env": env, "exit": exit_process, "run": run}


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self) -> None:
        super().__init__()
        self.redirect_count = 0

    def redirect_request(
        self,
        request: urllib.request.Request,
        response: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> urllib.request.Request | None:
        if self.redirect_count >= 5:
            raise urllib.error.HTTPError(
                request.full_url, code, "Redirect limit exceeded", headers, response
            )
        old = urllib.parse.urlsplit(request.full_url)
        new = urllib.parse.urlsplit(urllib.parse.urljoin(request.full_url, new_url))
        if (
            new.scheme not in ("http", "https")
            or not new.hostname
            or new.username is not None
            or new.password is not None
        ):
            raise ValueError(
                "HTTP redirects must target an HTTP(S) URL without user info."
            )
        if old.scheme == "https" and new.scheme != "https":
            raise ValueError("HTTPS redirects may not downgrade to HTTP.")
        redirected = super().redirect_request(
            request, response, code, message, headers, new.geturl()
        )
        if redirected is None:
            return None
        self.redirect_count += 1
        old_origin = (old.scheme, old.hostname, old.port)
        new_origin = (new.scheme, new.hostname, new.port)
        if old_origin != new_origin:
            for collection in (redirected.headers, redirected.unredirected_hdrs):
                for header in list(collection):
                    if header.casefold() in {
                        "authorization",
                        "cookie",
                        "proxy-authorization",
                    }:
                        redirected.remove_header(header)
        return redirected


def _http_functions() -> dict[str, Callable[..., Any]]:
    def request(
        url: str,
        method: str = "GET",
        body: str | bytes | bytearray | None = None,
        headers: dict[str, str] | None = None,
        timeout: int | float = 10.0,
        max_bytes: int = 1_048_576,
    ) -> dict[str, Any]:
        address = _string(url, "URL")
        parsed = urllib.parse.urlsplit(address)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("URL must be HTTP(S), include a host, and contain no user info.")
        verb = _string(method, "HTTP method").upper()
        if not verb.isascii() or not verb.isalpha():
            raise ValueError("HTTP method must contain only ASCII letters.")
        if body is None:
            payload = None
        elif isinstance(body, str):
            payload = body.encode("utf-8")
        elif isinstance(body, (bytes, bytearray)):
            payload = bytes(body)
        else:
            raise TypeError("HTTP body must be none, string, bytes, or bytearray.")
        if headers is None:
            request_headers: dict[str, str] = {}
        elif isinstance(headers, dict):
            request_headers = {}
            for name, value in headers.items():
                if not isinstance(name, str) or not isinstance(value, str):
                    raise TypeError("HTTP header names and values must be strings.")
                if "\r" in name or "\n" in name or "\r" in value or "\n" in value:
                    raise ValueError("HTTP headers must not contain line breaks.")
                request_headers[name] = value
        else:
            raise TypeError("HTTP headers must be a dictionary.")
        duration = _finite_number(timeout, "Timeout")
        if not 0 < duration <= 300:
            raise ValueError("Timeout must be greater than 0 and at most 300 seconds.")
        size_limit = _positive_integer(max_bytes, "Response limit", 67_108_864)
        handler = _SafeRedirectHandler()
        opener = urllib.request.build_opener(handler)
        http_request = urllib.request.Request(
            address, data=payload, headers=request_headers, method=verb
        )
        try:
            response = opener.open(http_request, timeout=duration)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            chunks = bytearray()
            while True:
                chunk = response.read(min(65536, size_limit + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
                if len(chunks) > size_limit:
                    raise ValueError(
                        f"HTTP response exceeded the {size_limit}-byte limit."
                    )
            return {
                "status": response.status,
                "headers": dict(response.headers.items()),
                "body": bytes(chunks),
            }

    return {"request": request}


def standard_module_functions(
    name: str,
    clock: Callable[[], float],
    random_source: random.Random,
    program_args: list[str],
) -> dict[str, Callable[..., Any]]:
    modules: dict[str, Callable[[], dict[str, Callable[..., Any]]]] = {
        "std.path": _path_functions,
        "std.fs": _filesystem_functions,
        "std.time": lambda: _time_functions(clock),
        "std.random": lambda: _random_functions(random_source),
        "std.math": _math_functions,
        "std.json": _json_functions,
        "std.encoding": _encoding_functions,
        "std.process": lambda: _process_functions(program_args),
        "std.http": _http_functions,
        "std.csv": _csv_functions,
        "std.url": _url_functions,
        "std.hash": _hash_functions,
    }
    return modules[name]()
