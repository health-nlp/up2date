"""Evaluate Task 3 study-inclusion submissions.

INPUT
  --predictions-tsv
      TSV columns: topic, study. Each row predicts that one candidate PMID is
      included in the updated review. Omitted candidates are predicted excluded.

GOLD DATA
  --pair-manifest
      Maps the initial and updated versions for each topic.
  --training-qrels
      Initial review candidate labels. Relevance 1 identifies already included PMIDs.
  --testing-qrels
      Updated review candidate labels. Relevance 1 identifies gold inclusions.

EVALUATION
  New candidates and new gold inclusions exclude PMIDs already included in the
  initial review. Predictions outside a topic's new candidate set are recorded
  as invalid and excluded from scoring. Reports precision, recall, F1, and F3
    per topic plus macro and micro aggregates. Topics with no new gold inclusions
    are excluded from macro aggregates and reported separately.

OUTPUT
  --metrics-out  Human-readable metric summary and top F3 topics.
  --report-json  Aggregate metrics, per-topic counts, and invalid predictions.
  --prototext-out
      TIRA-compatible aggregate metrics in evaluation.prototext format.

RUN
  python src/eval/task_3.py --predictions-tsv submission.tsv
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


DEFAULT_PREDICTIONS = Path("baselines/task_3/task3_predict_all_new_candidates.tsv")
DEFAULT_PAIR_MANIFEST = Path("datasets-for-tira/up2date-task-3/truths/review-version-pairs.csv")
DEFAULT_TRAINING_QRELS = Path("datasets-for-tira/up2date-task-3/truths/initial-review-qrels.txt")
DEFAULT_TESTING_QRELS = Path("datasets-for-tira/up2date-task-3/truths/updated-review-qrels.txt")
DEFAULT_METRICS_OUT = Path("baselines/task_3/eval/task3_eval_metrics.txt")
DEFAULT_REPORT_JSON = Path("baselines/task_3/eval/task3_eval_report.json")
DEFAULT_PROTOTEXT_OUT = Path("baselines/task_3/eval/evaluation.prototext")

PROTOTEXT_METRICS = (
    ("Macro Precision", "macro_precision"),
    ("Macro Recall", "macro_recall"),
    ("Macro F1", "macro_f1"),
    ("Macro F3", "macro_f3"),
    ("Micro Precision", "micro_precision"),
    ("Micro Recall", "micro_recall"),
    ("Micro F1", "micro_f1"),
    ("Micro F3", "micro_f3"),
)


def load_pair_versions(pair_manifest: Path) -> dict[str, tuple[str, str]]:
    if not pair_manifest.exists():
        raise SystemExit(f"Pair manifest does not exist: {pair_manifest}")
    pairs: dict[str, tuple[str, str]] = {}
    with pair_manifest.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            topic = (row.get("id") or "").strip()
            initial_version = (row.get("training_version") or "").strip()
            updated_version = (row.get("testing_version") or "").strip()
            if topic and initial_version and updated_version:
                pairs[topic] = (initial_version, updated_version)
    if not pairs:
        raise SystemExit(f"No version pairs found in: {pair_manifest}")
    return pairs


def load_qrels(qrels_path: Path) -> dict[str, dict[str, int]]:
    if not qrels_path.exists():
        raise SystemExit(f"Qrels file does not exist: {qrels_path}")
    qrels: dict[str, dict[str, int]] = defaultdict(dict)
    with qrels_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            fields = line.split()
            if len(fields) != 4:
                raise SystemExit(f"Expected four qrels columns in {qrels_path}:{line_number}")
            query_id, _, pmid, relevance = fields
            try:
                qrels[query_id][pmid] = int(relevance)
            except ValueError as error:
                raise SystemExit(f"Invalid relevance value in {qrels_path}:{line_number}") from error
    return dict(qrels)


def load_predictions(predictions_tsv: Path) -> dict[str, set[str]]:
    if not predictions_tsv.exists():
        raise SystemExit(f"Predictions file does not exist: {predictions_tsv}")
    predictions: dict[str, set[str]] = defaultdict(set)
    with predictions_tsv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")
        if set(("topic", "study")) - set(reader.fieldnames or []):
            raise SystemExit("Predictions TSV must contain 'topic' and 'study' columns.")
        for row in reader:
            topic = (row.get("topic") or "").strip()
            study = (row.get("study") or "").strip()
            if topic and study:
                predictions[topic].add(study)
    return dict(predictions)


def f_score(precision: float, recall: float, beta: float) -> float:
    if precision == 0.0 and recall == 0.0:
        return 0.0
    beta_squared = beta * beta
    return (1 + beta_squared) * precision * recall / (beta_squared * precision + recall)


def evaluate(
    pairs: dict[str, tuple[str, str]],
    initial_qrels: dict[str, dict[str, int]],
    updated_qrels: dict[str, dict[str, int]],
    predictions: dict[str, set[str]],
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    invalid_predictions: dict[str, list[str]] = {}

    for topic, (initial_version, updated_version) in sorted(pairs.items()):
        initial_labels = initial_qrels.get(f"{topic}_{initial_version}", {})
        updated_labels = updated_qrels.get(f"{topic}_{updated_version}", {})
        initial_included = {pmid for pmid, relevance in initial_labels.items() if relevance > 0}
        new_candidates = set(updated_labels) - initial_included
        new_included = {
            pmid for pmid, relevance in updated_labels.items() if relevance > 0 and pmid not in initial_included
        }
        submitted = predictions.get(topic, set())
        invalid = sorted(submitted - new_candidates)
        valid_predictions = submitted & new_candidates
        if invalid:
            invalid_predictions[topic] = invalid

        true_positives = valid_predictions & new_included
        precision = len(true_positives) / len(valid_predictions) if valid_predictions else 0.0
        recall = len(true_positives) / len(new_included) if new_included else 0.0
        rows.append(
            {
                "topic": topic,
                "new_candidates": len(new_candidates),
                "new_included": len(new_included),
                "predicted_included": len(valid_predictions),
                "true_positives": len(true_positives),
                "precision": precision,
                "recall": recall,
                "f1": f_score(precision, recall, 1.0),
                "f3": f_score(precision, recall, 3.0),
                "invalid_predictions": len(invalid),
            }
        )

    total_predicted = sum(int(row["predicted_included"]) for row in rows)
    total_included = sum(int(row["new_included"]) for row in rows)
    total_true_positives = sum(int(row["true_positives"]) for row in rows)
    micro_precision = total_true_positives / total_predicted if total_predicted else 0.0
    micro_recall = total_true_positives / total_included if total_included else 0.0
    macro_rows = [row for row in rows if int(row["new_included"]) > 0]
    summary = {
        "topics": len(rows),
        "macro_scored_topics": len(macro_rows),
        "zero_positive_topics": len(rows) - len(macro_rows),
        "macro_precision": statistics.mean(row["precision"] for row in macro_rows) if macro_rows else None,
        "macro_recall": statistics.mean(row["recall"] for row in macro_rows) if macro_rows else None,
        "macro_f1": statistics.mean(row["f1"] for row in macro_rows) if macro_rows else None,
        "macro_f3": statistics.mean(row["f3"] for row in macro_rows) if macro_rows else None,
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": f_score(micro_precision, micro_recall, 1.0),
        "micro_f3": f_score(micro_precision, micro_recall, 3.0),
        "predicted_included": total_predicted,
        "new_included": total_included,
        "true_positives": total_true_positives,
        "invalid_prediction_topics": len(invalid_predictions),
        "invalid_predictions": sum(len(studies) for studies in invalid_predictions.values()),
    }
    rows.sort(key=lambda row: float(row["f3"]), reverse=True)
    return {"summary": summary, "rows": rows, "invalid_predictions": invalid_predictions}


def render_metrics(report: dict[str, object], top_k: int) -> str:
    summary = report["summary"]
    rows = report["rows"]
    invalid_predictions = report["invalid_predictions"]
    assert isinstance(summary, dict)
    assert isinstance(rows, list)
    assert isinstance(invalid_predictions, dict)
    lines = [
        "Task 3 study classification evaluation",
        "------------------------------------",
        "Gold target: new studies included in the updated review.",
        f"Topics: {summary['topics']}",
        f"Topics in macro metrics: {summary['macro_scored_topics']}",
        f"Topics with zero positive studies: {summary['zero_positive_topics']}",
        f"Macro precision: {summary['macro_precision']:.3f}",
        f"Macro recall: {summary['macro_recall']:.3f}",
        f"Macro F1: {summary['macro_f1']:.3f}",
        f"Macro F3: {summary['macro_f3']:.3f}",
        f"Micro precision: {summary['micro_precision']:.3f}",
        f"Micro recall: {summary['micro_recall']:.3f}",
        f"Micro F1: {summary['micro_f1']:.3f}",
        f"Micro F3: {summary['micro_f3']:.3f}",
        f"True positives: {summary['true_positives']} / {summary['new_included']}",
        f"Predicted included studies: {summary['predicted_included']}",
        f"Invalid predictions: {summary['invalid_predictions']} across {summary['invalid_prediction_topics']} topics",
        "",
        f"Top {min(top_k, len(rows))} F3 scores",
        "topic\tprecision\trecall\tf1\tf3\ttrue_positives\tnew_included\tpredicted_included\tnew_candidates\tinvalid_predictions",
    ]
    for row in rows[:top_k]:
        lines.append(
            f"{row['topic']}\t{row['precision']:.3f}\t{row['recall']:.3f}\t{row['f1']:.3f}"
            f"\t{row['f3']:.3f}\t{row['true_positives']}\t{row['new_included']}"
            f"\t{row['predicted_included']}\t{row['new_candidates']}\t{row['invalid_predictions']}"
        )
    if invalid_predictions:
        lines.extend(["", "Invalid predicted studies by topic"])
        for topic, studies in sorted(invalid_predictions.items()):
            lines.append(f"{topic}: " + ", ".join(studies))
    return "\n".join(lines) + "\n"


def render_prototext(report: dict[str, object]) -> str:
    summary = report["summary"]
    assert isinstance(summary, dict)
    blocks: list[str] = []
    for display_name, metric_name in PROTOTEXT_METRICS:
        value = summary[metric_name]
        if not isinstance(value, (int, float)):
            raise ValueError(f"Metric {metric_name} is not numeric: {value!r}")
        blocks.append(f'measure{{\n  key: "{display_name}"\n  value: "{value}"\n}}')
    return "\n".join(blocks) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Task 3 study-inclusion predictions.")
    parser.add_argument("--predictions-tsv", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--pair-manifest", type=Path, default=DEFAULT_PAIR_MANIFEST)
    parser.add_argument("--training-qrels", type=Path, default=DEFAULT_TRAINING_QRELS)
    parser.add_argument("--testing-qrels", type=Path, default=DEFAULT_TESTING_QRELS)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--metrics-out", type=Path, default=DEFAULT_METRICS_OUT)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--prototext-out", type=Path, default=DEFAULT_PROTOTEXT_OUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = evaluate(
        load_pair_versions(args.pair_manifest),
        load_qrels(args.training_qrels),
        load_qrels(args.testing_qrels),
        load_predictions(args.predictions_tsv),
    )
    metrics = render_metrics(report, max(1, args.top_k))
    args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_out.write_text(metrics, encoding="utf-8")
    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    args.prototext_out.parent.mkdir(parents=True, exist_ok=True)
    args.prototext_out.write_text(render_prototext(report), encoding="utf-8")
    print(metrics, end="")


if __name__ == "__main__":
    main()