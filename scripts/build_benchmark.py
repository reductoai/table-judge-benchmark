from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from table_judge_benchmark.balanced import build_balanced_cases
from table_judge_benchmark.benchmark import load_manifest, write_manifest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the frozen benchmark")
    parser.add_argument(
        "--assignments",
        type=Path,
        default=Path("data/benchmark/error-type-assignments.json"),
    )
    parser.add_argument("--html-dir", type=Path, default=Path("data/benchmark/html"))
    parser.add_argument("--image-dir", type=Path, default=Path("data/benchmark/images"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if args.output_dir.exists():
        raise ValueError(f"output directory already exists: {args.output_dir}")

    assignments = json.loads(args.assignments.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True)
    assignments_path = args.output_dir / "error-type-assignments.json"
    assignments_path.write_bytes(args.assignments.read_bytes())
    cases = build_balanced_cases(
        args.html_dir,
        args.image_dir,
        args.seed,
        assignments,
    )
    manifest_path = args.output_dir / "manifest.jsonl"
    write_manifest(cases, manifest_path)
    load_manifest(manifest_path)

    print(json.dumps({
        "cases": len(cases),
        "error_types": {
            kind: sum(case.error.error_type == kind for case in cases)
            for kind in ("content", "formatting", "structure")
        },
        "content_subtypes": {
            kind: sum(case.error.error_subtype == kind for case in cases)
            for kind in ("wrong_cell_value", "misspelled_text")
        },
        "assignments_sha256": _sha256(assignments_path),
        "manifest_sha256": _sha256(manifest_path),
    }, indent=2))


if __name__ == "__main__":
    main()
