"""Evaluate Task 1 predicted update dates against the gold date of the updated review.

INPUT
    --predictions-tsv
            TSV columns: topic, date. Date format: YYYY-MM-DD.

GOLD DATA
    --topics-dir
        Input topic files defining the split and evaluation scope.
    --gold-topics-dir
        Updated review topic files. Uses each file's Date field as gold_date.

EVALUATION
    Date accuracy:
        - exact full-date match
        - exact year match
        - share of topics within 90 and within 180 days of the gold date
        - signed and absolute delta in days

OUTPUT
    --metrics-out  Human-readable aggregate date metrics.
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


DEFAULT_PREDICTIONS = Path("baselines/task_1/predictions.tsv")
DEFAULT_GOLD_TOPICS_DIR = Path("datasets-for-tira/up2date-task-1/truths/updated-review-topics")
DEFAULT_METRICS_OUT = Path("baselines/task_1/eval/task1-evaluation.txt")
DEFAULT_REPORT_JSON = Path("baselines/task_1/eval/task1-evaluation.json")
DEFAULT_PROTOTEXT_OUT = Path("baselines/task_1/eval/evaluation.prototext")

PROTOTEXT_METRICS = (
    ("Coverage", "coverage"),
    ("Full Date Accuracy", "full_date_accuracy"),
    ("Year Accuracy", "year_accuracy"),
    ("Mean Signed Delta Days", "mean_signed_delta_days"),
    ("Mean Absolute Delta Days", "mean_absolute_delta_days"),
    ("Within 90 Days Accuracy", "within_90_days_accuracy"),
    ("Within 180 Days Accuracy", "within_180_days_accuracy"),
)

TOLERANCE_DAYS = (90, 180)


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




TRACK_LABELS = {"track_a": "Track A", "track_b": "Track B"}


def track_label(track: str) -> str:
    return TRACK_LABELS.get(track, track.replace("_", " ").title())


UPDATE_TYPE_LABELS = {"new_content": "New content", "edit": "Edit"}


def update_type_label(update_type: str) -> str:
    return UPDATE_TYPE_LABELS.get(update_type, update_type.replace("_", " ").capitalize())


def read_topic_track(topic_path: Path) -> str | None:
    try:
        return read_topic_field(topic_path, "Track") or None
    except SystemExit:
        return None


def read_topic_update_type(topic_path: Path) -> str | None:
    try:
        return read_topic_field(topic_path, "UpdateType") or None
    except SystemExit:
        return None


def group_summaries(
    labels: dict[str, str | None],
    rows: list[dict[str, object]],
    topic_ids: list[str],
    missing_topics: list[str],
) -> dict[str, dict[str, object]] | None:
    """Summaries per label, only when every topic has one."""
    if not topic_ids or not all(labels.get(topic) for topic in topic_ids):
        return None
    grouped: dict[str, list[str]] = {}
    for topic in topic_ids:
        grouped.setdefault(str(labels[topic]), []).append(topic)
    return {
        label: summarize(
            [row for row in rows if row["topic"] in members],
            members,
            [topic for topic in missing_topics if topic in members],
        )
        for label, members in sorted(grouped.items())
    }


def summarize(rows: list[dict[str, object]], topic_ids: list[str], missing_topics: list[str]) -> dict[str, object]:
    tolerance = {
        f"within_{days}_days_accuracy": statistics.mean(int(row["absolute_delta_days"]) <= days for row in rows) if rows else None
        for days in TOLERANCE_DAYS
    }
    return {
        "gold_topics": len(topic_ids),
        "scored_topics": len(rows),
        "coverage": len(rows) / len(topic_ids) if topic_ids else 0.0,
        "full_date_accuracy": statistics.mean(row["full_date_match"] for row in rows) if rows else None,
        "year_accuracy": statistics.mean(row["year_match"] for row in rows) if rows else None,
        "mean_signed_delta_days": statistics.mean(row["delta_days"] for row in rows) if rows else None,
        "mean_absolute_delta_days": statistics.mean(row["absolute_delta_days"] for row in rows) if rows else None,
        **tolerance,
        "missing_topics": missing_topics,
    }


def evaluate(
    topic_ids: list[str],
    gold_topics_dir: Path,
    predictions: dict[str, dt.date],
    by_track: bool = True,
    by_update_type: bool = True,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    missing_topics: list[str] = []
    tracks: dict[str, str | None] = {}
    update_types: dict[str, str | None] = {}

    for topic in topic_ids:
        predicted_date = predictions.get(topic)
        if predicted_date is None:
            missing_topics.append(topic)
            continue

        gold_path = resolve_topic_path(gold_topics_dir, topic)
        gold_date = read_topic_date(gold_path)
        tracks[topic] = read_topic_track(gold_path)
        update_types[topic] = read_topic_update_type(gold_path)
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
            }
        )

    report: dict[str, object] = {"summary": summarize(rows, topic_ids, missing_topics)}
    for enabled, key, labels in ((by_track, "by_track", tracks), (by_update_type, "by_update_type", update_types)):
        groups = group_summaries(labels, rows, topic_ids, missing_topics) if enabled else None
        if groups is not None:
            report[key] = groups
    rows.sort(key=lambda row: int(row["absolute_delta_days"]), reverse=True)
    report["rows"] = rows
    return report


def render_metrics(report: dict[str, object], top_k: int) -> str:
    summary = report["summary"]
    rows = report["rows"]
    assert isinstance(summary, dict)
    assert isinstance(rows, list)
    lines = [
        "Task 1 evaluation",
        "-----------------",
        "Date gold target: Date field in the updated-review topic.",
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
                f"Within 90 days accuracy: {summary['within_90_days_accuracy']:.3f}",
                f"Within 180 days accuracy: {summary['within_180_days_accuracy']:.3f}",
            ]
        )
    if summary["missing_topics"]:
        lines.append("Missing predictions: " + ", ".join(summary["missing_topics"]))
    def show(value: object, digits: int = 3) -> str:
        return "n/a" if value is None else f"{value:.{digits}f}"

    for key, title, name, label_of in (
        ("by_track", "By track", "track", track_label),
        ("by_update_type", "By update type", "update_type", update_type_label),
    ):
        groups = report.get(key)
        if not isinstance(groups, dict):
            continue
        lines.extend(["", title, f"{name}\ttopics\tfull_date_accuracy\tyear_accuracy\tmean_abs_delta_days\twithin_90_days\twithin_180_days"])
        for label, part in groups.items():
            lines.append(
                f"{label_of(label)}\t{part['scored_topics']}\t{show(part['full_date_accuracy'])}\t{show(part['year_accuracy'])}"
                f"\t{show(part['mean_absolute_delta_days'], 1)}\t{show(part['within_90_days_accuracy'])}\t{show(part['within_180_days_accuracy'])}"
            )
    lines.extend(["", f"Top {min(top_k, len(rows))} absolute date deltas"])
    lines.append("topic\tgold_date\tpredicted_date\tdelta_days")
    for row in rows[:top_k]:
        lines.append(f"{row['topic']}\t{row['gold_date']}\t{row['predicted_date']}\t{row['delta_days']}")
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
    for key, label_of in (("by_track", track_label), ("by_update_type", update_type_label)):
        groups = report.get(key)
        if not isinstance(groups, dict):
            continue
        for label, part in groups.items():
            for display_name, metric_name in PROTOTEXT_METRICS:
                value = part[metric_name]
                if value is None:
                    continue
                blocks.append(f'measure{{\n  key: "{label_of(label)} {display_name}"\n  value: "{value}"\n}}')
    return "\n".join(blocks) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Task 1 predicted dates offline.")
    parser.add_argument("--predictions-tsv", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument(
        "--topics-dir",
        type=Path,
        help="Input topic directory defining the topics to score.",
    )
    parser.add_argument("--gold-topics-dir", type=Path, default=DEFAULT_GOLD_TOPICS_DIR)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--metrics-out", type=Path, default=DEFAULT_METRICS_OUT)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--prototext-out", type=Path, default=DEFAULT_PROTOTEXT_OUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    topic_ids = read_topic_ids(args.topics_dir or args.gold_topics_dir)
    report = evaluate(
        topic_ids,
        args.gold_topics_dir,
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