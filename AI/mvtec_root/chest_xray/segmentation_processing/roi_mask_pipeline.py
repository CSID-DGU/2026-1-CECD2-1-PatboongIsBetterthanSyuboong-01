from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable, List, Tuple

from .hybridgnet_segmenter import HybridGNetSegmenter, _normalize_rel_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Filter CheXpert data to PA view and apply ROI masking.")
    parser.add_argument(
        "--source_root",
        type=Path,
        default=Path("mvtec_root/chest_xray/archive"),
        help="Root directory containing the original CheXpert train/valid folders and CSVs.",
    )
    parser.add_argument(
        "--target_root",
        type=Path,
        default=Path("mvtec_root/chest_xray/archive_pa"),
        help="Destination root for the PA-only, ROI-masked dataset.",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="Torch device (e.g. cuda:0 / cpu). Defaults to CUDA if available.",
    )
    parser.add_argument(
        "--weights",
        type=Path,
        default=None,
        help="Optional path to HybridGNet weights. Defaults to CheXmask weights.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip images that already have a masked copy in the target directory.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N samples for quick dry-runs.",
    )
    return parser.parse_args()


def _is_pa_frontal(row: dict) -> bool:
    view = (row.get("AP/PA") or "").strip().upper()
    plane = (row.get("Frontal/Lateral") or "").strip().upper()
    return view == "PA" and (plane == "FRONTAL" or plane == "FRONTAL ")


def _filter_rows(rows: Iterable[dict]) -> List[dict]:
    return [row for row in rows if _is_pa_frontal(row)]


def _copy_and_mask(
    row: dict,
    segmenter: HybridGNetSegmenter,
    source_root: Path,
    target_root: Path,
    skip_existing: bool,
) -> Tuple[bool, Path]:
    rel_path = _normalize_rel_path(row["Path"])
    source_path = (source_root / rel_path).resolve()
    target_path = (target_root / rel_path).resolve()

    if not source_path.exists():
        raise FileNotFoundError(f"Missing image referenced in CSV: {source_path}")

    segmenter.apply_mask(source_path, target_path, skip_if_exists=skip_existing)
    return True, target_path


def _process_split(
    split: str,
    segmenter: HybridGNetSegmenter,
    args: argparse.Namespace,
) -> None:
    source_csv = args.source_root / f"{split}.csv"
    target_csv = args.target_root / f"{split}.csv"
    if not source_csv.exists():
        raise FileNotFoundError(f"Expected CSV not found: {source_csv}")

    target_csv.parent.mkdir(parents=True, exist_ok=True)

    with source_csv.open("r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    filtered_rows = _filter_rows(reader)
    if not filtered_rows:
        raise RuntimeError(f"No PA/Frontal samples found in {source_csv}")

    processed_rows: List[dict] = []
    processed = 0
    for row in filtered_rows:
        try:
            _copy_and_mask(row, segmenter, args.source_root, args.target_root, args.skip_existing)
        except FileNotFoundError as exc:
            print(f"[WARN] {exc}. Skipping.")
            continue
        processed += 1
        processed_rows.append(row)
        if args.limit and processed >= args.limit:
            break
        if processed % 250 == 0:
            print(f"[{split}] Processed {processed} samples...")

    fieldnames = reader[0].keys()
    with target_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(processed_rows)

    print(f"[{split}] Done. Saved {len(processed_rows)} PA samples to {target_csv}")


def main() -> None:
    args = _parse_args()
    args.source_root = args.source_root.resolve()
    args.target_root = args.target_root.resolve()
    args.target_root.mkdir(parents=True, exist_ok=True)

    segmenter = HybridGNetSegmenter(device=args.device, weights_path=args.weights)
    for split in ("train", "valid"):
        _process_split(split, segmenter, args)


if __name__ == "__main__":
    main()

