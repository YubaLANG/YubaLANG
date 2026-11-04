import argparse
from datetime import datetime, timezone
import gzip
import io
from pathlib import Path
import stat
import tarfile
import zipfile


ZIP_EPOCH = 315532800


def _zip_timestamp(source_date_epoch: int) -> tuple[int, int, int, int, int, int]:
    timestamp = max(source_date_epoch, ZIP_EPOCH)
    date = datetime.fromtimestamp(timestamp, timezone.utc)
    return (
        date.year,
        date.month,
        date.day,
        date.hour,
        date.minute,
        date.second // 2 * 2,
    )


def create_archive(
    binary: Path,
    output: Path,
    archive_format: str,
    source_date_epoch: int,
) -> None:
    payload = binary.read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)

    if archive_format == "zip":
        info = zipfile.ZipInfo(binary.name, _zip_timestamp(source_date_epoch))
        info.create_system = 3
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (stat.S_IFREG | 0o755) << 16
        with zipfile.ZipFile(
            output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        return

    if archive_format == "tar.gz":
        with output.open("wb") as archive_file:
            with gzip.GzipFile(
                filename="", mode="wb", fileobj=archive_file, mtime=0
            ) as compressed:
                with tarfile.open(
                    fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT
                ) as archive:
                    info = tarfile.TarInfo(binary.name)
                    info.size = len(payload)
                    info.mode = 0o755
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = source_date_epoch
                    archive.addfile(info, io.BytesIO(payload))
        return

    raise ValueError(f"Unsupported release archive format: {archive_format}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a release archive with normalized metadata."
    )
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("zip", "tar.gz"), required=True)
    parser.add_argument("--source-date-epoch", type=int, required=True)
    arguments = parser.parse_args()
    create_archive(
        arguments.binary,
        arguments.output,
        arguments.format,
        arguments.source_date_epoch,
    )


if __name__ == "__main__":
    main()
