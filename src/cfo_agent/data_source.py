from __future__ import annotations

from pathlib import Path


class DataSourceError(ValueError):
    pass


def resolve_input_csv(input_csv: str | None, input_dir: str | None, input_glob: str) -> str:
    if input_csv:
        path = Path(input_csv)
        if not path.exists() or not path.is_file():
            raise DataSourceError(f"Input CSV not found: {path}")
        return str(path)

    if not input_dir:
        raise DataSourceError("Either --input or --input-dir must be provided.")

    base = Path(input_dir)
    if not base.exists() or not base.is_dir():
        raise DataSourceError(f"Input directory not found: {base}")

    candidates = [p for p in base.glob(input_glob) if p.is_file()]
    if not candidates:
        raise DataSourceError(
            f"No CSV files found in {base} with glob pattern '{input_glob}'."
        )

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return str(latest)
