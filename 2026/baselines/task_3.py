"""Build a recall-oriented Task 3 predict-all-candidates baseline.

INPUT
    --candidates-tsv
            Public Task 3 candidate release with TSV columns: topic, study.

METHOD
    Copies every public candidate into the prediction. This is a high-recall,
    low-precision baseline and does not require private qrels or labels.

OUTPUT
    --output-tsv
            TSV columns: topic, study. One row predicts one study as included.

RUN
    python3 2026/baselines/task_3.py
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_CANDIDATES_TSV = Path("2026/up2date-task-3-test/inputs/candidates.tsv")
DEFAULT_OUTPUT_TSV = Path("2026/baseline-output/task-3-test/predictions.tsv")


def load_candidates(candidates_tsv: Path) -> list[tuple[str, str]]:
    if not candidates_tsv.exists():
        raise SystemExit(f"Candidates file does not exist: {candidates_tsv}")
    candidates: set[tuple[str, str]] = set()
    with candidates_tsv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")
        if set(("topic", "study")) - set(reader.fieldnames or []):
            raise SystemExit("Candidates TSV must contain 'topic' and 'study' columns.")
        for row in reader:
            topic = (row.get("topic") or "").strip()
            study = (row.get("study") or "").strip()
            if topic and study:
                candidates.add((topic, study))
    if not candidates:
        raise SystemExit(f"No candidates found in: {candidates_tsv}")
    return sorted(candidates)


def write_tsv(output_tsv: Path, predictions: list[tuple[str, str]]) -> None:
    output_tsv.parent.mkdir(parents=True, exist_ok=True)
    with output_tsv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, delimiter="\t")
        writer.writerow(["topic", "study"])
        writer.writerows(predictions)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the Task 3 predict-all-candidates baseline.")
    parser.add_argument("--candidates-tsv", type=Path, default=DEFAULT_CANDIDATES_TSV)
    parser.add_argument("--output-tsv", type=Path, default=DEFAULT_OUTPUT_TSV)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    predictions = load_candidates(args.candidates_tsv)
    write_tsv(args.output_tsv, predictions)
    print(f"Wrote {len(predictions)} Task 3 predicted included studies to: {args.output_tsv}")


if __name__ == "__main__":
    main()