from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from ktl_backend.config import RAW_DOMAIN_DIRS, data_processed_root, data_raw_root, project_root
from ktl_backend.schemas.manifest import ManifestFileEntry, ManifestRun


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_inventory_files() -> list[ManifestFileEntry]:
    entries: list[ManifestFileEntry] = []
    raw_root = data_raw_root()
    for domain in RAW_DOMAIN_DIRS:
        domain_dir = raw_root / domain
        if not domain_dir.is_dir():
            continue
        for path in sorted(domain_dir.rglob("*")):
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            rel = path.relative_to(domain_dir).as_posix()
            entries.append(
                ManifestFileEntry.model_validate(
                    {
                        "domain": domain,
                        "relative_path": rel,
                        "sha256": _sha256_file(path),
                        "size_bytes": path.stat().st_size,
                        "suffix": path.suffix.lower(),
                    }
                )
            )
    entries.sort(key=lambda item: (item.domain, item.relative_path))
    return entries


def run_ingest() -> ManifestRun:
    """
    Scan `data/raw/**`, compute checksums, write manifests under `data/processed/manifests/`.
    """
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest = ManifestRun(run_id=run_id, files=_iter_inventory_files())

    out_dir = data_processed_root() / "manifests"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = manifest.model_dump(mode="json")
    (out_dir / f"{run_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out_dir / "latest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    manifest = run_ingest()
    root = project_root()
    print(f"Wrote manifests for {len(manifest.files)} files under {root / 'data' / 'processed' / 'manifests'}")


if __name__ == "__main__":
    main()
