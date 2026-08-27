"""Evaluate Task 1 predicted update dates against offline cutoff gold data.

INPUT
    --predictions-tsv
            TSV columns: topic, date. Date format: YYYY-MM-DD.

GOLD DATA
    --gold-topics-dir
        Updated review topic files. Uses each file's Date field as gold_date.
    --cutoff-gold-tsv
        Precomputed gold TSV columns: topic, pmid, publication_year. Contains
        each newly relevant PMID and the date field from the frozen collection.

EVALUATION
    Date accuracy:
        - exact full-date match
        - exact year match
        - signed and absolute delta in days
    Offline cutoff recall:
        - relevant PMIDs are supplied in the precomputed cutoff gold TSV
        - counts newly relevant PMIDs published by the predicted year
        - no URL, query execution, or retrieval occurs during evaluation

OUTPUT
    --metrics-out  Human-readable aggregate date and cutoff-recall metrics.
    --report-json  Aggregate metrics and per-topic values.
    --prototext-out
        TIRA-compatible aggregate metrics in evaluation.prototext format.

RUN
    python src/eval/task_1.py --predictions-tsv submission.tsv
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import statistics
from pathlib import Path


DEFAULT_PREDICTIONS = Path("baselines/task_1/task1_demo_predictions.tsv")
DEFAULT_GOLD_TOPICS_DIR = Path("datasets-for-tira/up2date-task-1/truths/updated-review-topics")
DEFAULT_CUTOFF_GOLD = Path("datasets-for-tira/up2date-task-1/truths/cutoff-gold.tsv")
DEFAULT_METRICS_OUT = Path("baselines/task_1/eval/task1_eval_metrics.txt")
DEFAULT_REPORT_JSON = Path("baselines/task_1/eval/task1_eval_report.json")
DEFAULT_PROTOTEXT_OUT = Path("baselines/task_1/eval/evaluation.prototext")

PROTOTEXT_METRICS = (
    ("Coverage", "coverage"),
    ("Full Date Accuracy", "full_date_accuracy"),
    ("Year Accuracy", "year_accuracy"),
    ("Mean Signed Delta Days", "mean_signed_delta_days"),
    ("Mean Absolute Delta Days", "mean_absolute_delta_days"),
    ("Macro Recall", "macro_recall"),
    ("Micro Recall", "micro_recall"),
)


def read_topic_ids(topics_dir: Path) -> list[str]:
    if not topics_dir.exists():
        raise SystemExit(f"Topics directory does not exist: {topics_dir}")
    topic_ids = sorted(path.stem for path in topics_dir.iterdir() if path.is_file())
    if not topic_ids:
        raise SystemExit(f"No topic files found in: {topics_dir}")
    return topic_ids


def resolve_topic_path(topics_dir: Path, topic: str) -> Path:
    topic_path = topics_dir / topic
    if topic_path.exists():
        return topic_path
    return topics_dir / f"{topic}.txt"


def read_topic_field(topic_path: Path, field_name: str) -> str:
    if not topic_path.exists():
        raise SystemExit(f"Topic file does not exist: {topic_path}")
    for line in topic_path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip().lower() == field_name.lower():
            return value.strip()
    raise SystemExit(f"No {field_name!r} field found in {topic_path}")


def read_topic_date(topic_path: Path) -> dt.date:
    value = read_topic_field(topic_path, "Date")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as error:
        raise SystemExit(f"Invalid Date field in {topic_path}: {value!r}") from error


def load_predictions(predictions_tsv: Path) -> dict[str, dt.date]:
    if not predictions_tsv.exists():
        raise SystemExit(f"Predictions file does not exist: {predictions_tsv}")
    predictions: dict[str, dt.date] = {}
    with predictions_tsv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")
        if set(("topic", "date")) - set(reader.fieldnames or []):
            raise SystemExit("Predictions TSV must contain 'topic' and 'date' columns.")
        for row in reader:
            topic = (row.get("topic") or "").strip()
            date_text = (row.get("date") or "").strip()
            if not topic or not date_text:
                continue
            try:
                predictions[topic] = dt.date.fromisoformat(date_text)
            except ValueError as error:
                raise SystemExit(f"Invalid prediction date for {topic}: {date_text!r}") from error
    return predictions


def load_cutoff_gold(cutoff_gold_tsv: Path) -> dict[str, dict[str, int]]:
    if not cutoff_gold_tsv.exists():
        raise SystemExit(
            f"Cutoff gold file does not exist: {cutoff_gold_tsv}. "
            "Prepare it from the frozen collection before evaluation."
        )
    gold: dict[str, dict[str, int]] = {}
    with cutoff_gold_tsv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")
        required = {"topic", "pmid", "publication_year"}
        if required - set(reader.fieldnames or []):
            raise SystemExit("Cutoff gold TSV must contain topic, pmid, and publication_year columns.")
        for row_number, row in enumerate(reader, start=2):
            topic = (row.get("topic") or "").strip()
            pmid = (row.get("pmid") or "").strip()
            year_text = (row.get("publication_year") or "").strip()
            if not topic or not pmid or not year_text:
                raise SystemExit(f"Missing cutoff gold value at {cutoff_gold_tsv}:{row_number}")
            try:
                year = int(year_text)
            except ValueError as error:
                raise SystemExit(f"Invalid publication year at {cutoff_gold_tsv}:{row_number}: {year_text!r}") from error
            previous = gold.setdefault(topic, {}).get(pmid)
            if previous is not None and previous != year:
                raise SystemExit(f"Conflicting publication years for {topic}/{pmid} in {cutoff_gold_tsv}")
            gold[topic][pmid] = year
    return gold


def evaluate(
    topic_ids: list[str],
    gold_topics_dir: Path,
    predictions: dict[str, dt.date],
    cutoff_gold: dict[str, dict[str, int]],
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    missing_topics: list[str] = []

    for topic in topic_ids:
        predicted_date = predictions.get(topic)
        if predicted_date is None:
            missing_topics.append(topic)
            continue

        gold_date = read_topic_date(resolve_topic_path(gold_topics_dir, topic))
        relevant_years = cutoff_gold.get(topic, {})
        covered_pmids = {
            pmid
            for pmid, publication_year in relevant_years.items()
            if publication_year <= predicted_date.year
        }
        recall = len(covered_pmids) / len(relevant_years) if relevant_years else None
        delta_days = (predicted_date - gold_date).days
        rows.append(
            {
                "topic": topic,
                "gold_date": gold_date.isoformat(),
                "predicted_date": predicted_date.isoformat(),
                "full_date_match": predicted_date == gold_date,
                "year_match": predicted_date.year == gold_date.year,
                "delta_days": delta_days,
                "absolute_delta_days": abs(delta_days),
                "new_relevant_pmids": len(relevant_years),
                "covered_relevant_pmids": len(covered_pmids),
                "recall": recall,
            }
        )

    recall_rows = [row for row in rows if row["recall"] is not None]
    total_relevant = sum(int(row["new_relevant_pmids"]) for row in recall_rows)
    total_covered = sum(int(row["covered_relevant_pmids"]) for row in recall_rows)
    summary = {
        "gold_topics": len(topic_ids),
        "scored_topics": len(rows),
        "coverage": len(rows) / len(topic_ids),
        "full_date_accuracy": statistics.mean(row["full_date_match"] for row in rows) if rows else None,
        "year_accuracy": statistics.mean(row["year_match"] for row in rows) if rows else None,
        "mean_signed_delta_days": statistics.mean(row["delta_days"] for row in rows) if rows else None,
        "mean_absolute_delta_days": statistics.mean(row["absolute_delta_days"] for row in rows) if rows else None,
        "macro_recall": statistics.mean(row["recall"] for row in recall_rows) if recall_rows else None,
        "micro_recall": total_covered / total_relevant if total_relevant else None,
        "new_relevant_pmids": sum(int(row["new_relevant_pmids"]) for row in rows),
        "covered_relevant_pmids": total_covered,
        "missing_topics": missing_topics,
    }
    rows.sort(key=lambda row: int(row["absolute_delta_days"]), reverse=True)
    return {"summary": summary, "rows": rows}


def render_metrics(report: dict[str, object], top_k: int) -> str:
    summary = report["summary"]
    rows = report["rows"]
    assert isinstance(summary, dict)
    assert isinstance(rows, list)
    lines = [
        "Task 1 evaluation",
        "-----------------",
        "Date gold target: Date field in the updated-review topic.",
        "Recall target: new relevant PMIDs covered by the submitted cutoff year.",
        f"Gold topics: {summary['gold_topics']}",
        f"Scored topics: {summary['scored_topics']}",
        f"Coverage: {summary['coverage']:.3f}",
    ]
    if summary["full_date_accuracy"] is not None:
        lines.extend(
            [
                f"Full-date accuracy: {summary['full_date_accuracy']:.3f}",
                f"Year accuracy: {summary['year_accuracy']:.3f}",
                f"Mean signed delta (days): {summary['mean_signed_delta_days']:.3f}",
                f"Mean absolute delta (days): {summary['mean_absolute_delta_days']:.3f}",
                f"Macro cutoff recall: {summary['macro_recall']:.3f}",
                f"Micro recall: {summary['micro_recall']:.3f}",
                f"Covered relevant PMIDs: {summary['covered_relevant_pmids']} / {summary['new_relevant_pmids']}",
            ]
        )
    if summary["missing_topics"]:
        lines.append("Missing predictions: " + ", ".join(summary["missing_topics"]))
    lines.extend(["", f"Top {min(top_k, len(rows))} absolute date deltas"])
    lines.append("topic\tgold_date\tpredicted_date\tdelta_days\trecall\tcovered_relevant_pmids\tnew_relevant_pmids")
    for row in rows[:top_k]:
        recall = "n/a" if row["recall"] is None else f"{row['recall']:.3f}"
        lines.append(
            f"{row['topic']}\t{row['gold_date']}\t{row['predicted_date']}"
            f"\t{row['delta_days']}\t{recall}"
            f"\t{row['covered_relevant_pmids']}\t{row['new_relevant_pmids']}"
        )
    return "\n".join(lines) + "\n"


def render_prototext(report: dict[str, object]) -> str:
    summary = report["summary"]
    assert isinstance(summary, dict)
    blocks: list[str] = []
    for display_name, metric_name in PROTOTEXT_METRICS:
        value = summary[metric_name]
        if value is None:
            continue
        if not isinstance(value, (int, float)):
            raise ValueError(f"Metric {metric_name} is not numeric: {value!r}")
        blocks.append(f'measure{{\n  key: "{display_name}"\n  value: "{value}"\n}}')
    return "\n".join(blocks) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Task 1 predicted dates offline.")
    parser.add_argument("--predictions-tsv", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--gold-topics-dir", type=Path, default=DEFAULT_GOLD_TOPICS_DIR)
    parser.add_argument("--cutoff-gold-tsv", type=Path, default=DEFAULT_CUTOFF_GOLD)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--metrics-out", type=Path, default=DEFAULT_METRICS_OUT)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--prototext-out", type=Path, default=DEFAULT_PROTOTEXT_OUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = evaluate(
        read_topic_ids(args.gold_topics_dir),
        args.gold_topics_dir,
        load_predictions(args.predictions_tsv),
        load_cutoff_gold(args.cutoff_gold_tsv),
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