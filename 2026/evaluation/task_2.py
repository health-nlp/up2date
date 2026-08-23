"""Evaluate Task 2 Boolean-query submissions against updated-review qrels.

INPUT
    --predictions-tsv
            TSV columns: topic, query.
    --topics-dir
            Initial review topic IDs to evaluate.

GOLD DATA
    --gold-topics-dir
            Updated topic files. The Version field selects the matching qrels topic.
    --qrels
            Included PMIDs for each updated review version.

EVALUATION
    - Executes each submitted query through Orbit ESearch (--orbit-api-base).
    - Retrieves every result page in batches of 1,000 PMIDs.
    - Compares retrieved PMIDs with updated-review included PMIDs.
    - Reports precision, recall, F1, and F3 per topic, plus macro and micro scores.

ROBUSTNESS
    - Checkpoints --report-json after every completed topic.
    - Records invalid or failing queries without aborting the rest of the run.
    - --resume continues from successfully completed checkpoint rows.
    - --validate-only executes one page per query to preflight a submission.

OUTPUT
    --metrics-out  Human-readable aggregate metrics, top F3 topics, and failures.
    --report-json  Aggregate metrics, scored rows, validation rows, and failures.
    --prototext-out
        TIRA-compatible aggregate metrics in evaluation.prototext format.

RUN
    python src/eval/task_2.py --validate-only  # preflight submitted queries
    python src/eval/task_2.py                  # full evaluation
    python src/eval/task_2.py --resume         # continue a checkpointed run
"""

from __future__ import annotations

import argparse
import csv
import json
import socket
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tqdm import tqdm


DEFAULT_PREDICTIONS = Path("baselines/task_2/task2_initial_query_baseline.tsv")
DEFAULT_TOPICS_DIR = Path("export/training/topics")
DEFAULT_GOLD_TOPICS_DIR = Path("export/testing/topics")
DEFAULT_QRELS = Path("export/testing/qrels_included_only.txt")
DEFAULT_ORBIT_API_BASE = "https://orbit-api.health-nlp.com"
DEFAULT_METRICS_OUT = Path("baselines/task_2/eval/task2_eval_metrics.txt")
DEFAULT_REPORT_JSON = Path("baselines/task_2/eval/task2_eval_report.json")
DEFAULT_PROTOTEXT_OUT = Path("baselines/task_2/eval/evaluation.prototext")
PAGE_SIZE = 1000
REQUEST_TIMEOUT_SECONDS = 60
REQUEST_INTERVAL_SECONDS = 0.2
MAX_RETRIES = 5

PROTOTEXT_METRICS = (
    ("Coverage", "coverage"),
    ("Macro Precision", "macro_precision"),
    ("Macro Recall", "macro_recall"),
    ("Macro F1", "macro_f1"),
    ("Macro F3", "macro_f3"),
    ("Micro Precision", "micro_precision"),
    ("Micro Recall", "micro_recall"),
    ("Micro F1", "micro_f1"),
    ("Micro F3", "micro_f3"),
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


def read_topic_version(topic_path: Path) -> str:
    if not topic_path.exists():
        raise SystemExit(f"Gold topic file does not exist: {topic_path}")
    for line in topic_path.read_text(encoding="utf-8", errors="replace").splitlines():
        key, separator, value = line.partition(":")
        if separator and key.strip().lower() == "version":
            version = value.strip()
            if version:
                return version
    raise SystemExit(f"No Version field found in {topic_path}")


def load_predictions(predictions_tsv: Path) -> dict[str, str]:
    if not predictions_tsv.exists():
        raise SystemExit(f"Predictions file does not exist: {predictions_tsv}")
    predictions: dict[str, str] = {}
    with predictions_tsv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")
        if set(("topic", "query")) - set(reader.fieldnames or []):
            raise SystemExit("Predictions TSV must contain 'topic' and 'query' columns.")
        for row in reader:
            topic = (row.get("topic") or "").strip()
            query = (row.get("query") or "").strip()
            if topic and query:
                predictions[topic] = query
    return predictions


def load_included_qrels(qrels_path: Path) -> dict[str, set[str]]:
    if not qrels_path.exists():
        raise SystemExit(f"Qrels file does not exist: {qrels_path}")
    included: dict[str, set[str]] = defaultdict(set)
    with qrels_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            fields = line.split()
            if len(fields) != 4:
                raise SystemExit(f"Expected four qrels columns in {qrels_path}:{line_number}")
            query_id, _, pmid, relevance = fields
            if relevance == "1":
                included[query_id].add(pmid)
    return dict(included)


def f_score(precision: float, recall: float, beta: float) -> float:
    if precision == 0.0 and recall == 0.0:
        return 0.0
    beta_squared = beta * beta
    return (1 + beta_squared) * precision * recall / (beta_squared * precision + recall)


def fetch_json(api_base: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}/entrez/eutils/esearch.fcgi?{urlencode(params)}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "up2date-task2-evaluator/1.0"})
    for attempt in range(MAX_RETRIES):
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.load(response)
            time.sleep(REQUEST_INTERVAL_SECONDS)
            return payload
        except HTTPError as error:
            if error.code != 429 or attempt == MAX_RETRIES - 1:
                raise
            retry_after = error.headers.get("Retry-After")
            time.sleep(float(retry_after) if retry_after else (attempt + 1) * 2)
        except (TimeoutError, socket.timeout, URLError):
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep((attempt + 1) * 2)
    raise RuntimeError("Unreachable Orbit retry state")


def run_query(api_base: str, query: str) -> tuple[set[str], int]:
    retrieved: set[str] = set()
    retstart = 0
    total_results: int | None = None

    while True:
        payload = fetch_json(
            api_base,
            {"term": query, "retmode": "json", "retmax": PAGE_SIZE, "retstart": retstart},
        )
        search_result = payload.get("esearchresult") or payload.get("esearch") or {}
        if total_results is None:
            try:
                total_results = int(search_result.get("count", 0))
            except (TypeError, ValueError):
                total_results = 0
        batch_ids = [str(pmid) for pmid in (search_result.get("idlist") or [])]
        if not batch_ids:
            break
        retrieved.update(batch_ids)
        retstart += len(batch_ids)
        if len(batch_ids) < PAGE_SIZE:
            break

    total_results = total_results if total_results is not None else 0
    return retrieved, total_results


def validate_query(api_base: str, query: str) -> int:
    payload = fetch_json(
        api_base,
        {"term": query, "retmode": "json", "retmax": 1, "retstart": 0},
    )
    search_result = payload.get("esearchresult") or payload.get("esearch") or {}
    try:
        return int(search_result.get("count", 0))
    except (TypeError, ValueError):
        return 0


def evaluate(
    topic_ids: list[str],
    gold_topics_dir: Path,
    predictions: dict[str, str],
    qrels: dict[str, set[str]],
    orbit_api_base: str,
    checkpoint: Callable[[dict[str, object]], None] | None = None,
    completed_rows: list[dict[str, object]] | None = None,
    validate_only: bool = False,
) -> dict[str, object]:
    rows = list(completed_rows or [])
    completed_topics = {
        str(row["topic"])
        for row in rows
        if row.get("execution_error") is None
    }
    missing_topics: list[str] = []

    for topic in tqdm(topic_ids, desc="Executing Task 2 queries", unit="topic"):
        if topic in completed_topics:
            continue
        query = predictions.get(topic)
        if query is None:
            missing_topics.append(topic)
            continue
        version = read_topic_version(resolve_topic_path(gold_topics_dir, topic))
        relevant = qrels.get(f"{topic}_{version}", set())
        try:
            if validate_only:
                total_results = validate_query(orbit_api_base, query)
                rows.append(
                    {
                        "topic": topic,
                        "updated_version": version,
                        "query": query,
                        "reported_total_results": total_results,
                        "validation_only": True,
                        "execution_error": None,
                    }
                )
                if checkpoint is not None:
                    checkpoint(build_report(topic_ids, rows, missing_topics))
                continue
            retrieved, total_results = run_query(orbit_api_base, query)
        except (HTTPError, TimeoutError, socket.timeout, URLError, RuntimeError) as error:
            rows.append(
                {
                    "topic": topic,
                    "updated_version": version,
                    "query": query,
                    "execution_error": f"{type(error).__name__}: {error}",
                }
            )
            if checkpoint is not None:
                checkpoint(build_report(topic_ids, rows, missing_topics))
            continue
        relevant_retrieved = relevant & retrieved
        precision = len(relevant_retrieved) / len(retrieved) if retrieved else 0.0
        recall = len(relevant_retrieved) / len(relevant) if relevant else 0.0
        rows.append(
            {
                "topic": topic,
                "updated_version": version,
                "query": query,
                "retrieved": len(retrieved),
                "reported_total_results": total_results,
                "execution_error": None,
                "relevant": len(relevant),
                "relevant_retrieved": len(relevant_retrieved),
                "precision": precision,
                "recall": recall,
                "f1": f_score(precision, recall, 1.0),
                "f3": f_score(precision, recall, 3.0),
            }
        )
        if checkpoint is not None:
            checkpoint(build_report(topic_ids, rows, missing_topics))

    return build_report(topic_ids, rows, missing_topics)


def build_report(
    topic_ids: list[str], rows: list[dict[str, object]], missing_topics: list[str]
) -> dict[str, object]:

    scored_rows = [row for row in rows if row.get("execution_error") is None and "precision" in row]
    validation_rows = [row for row in rows if row.get("validation_only")]
    failed_rows = [row for row in rows if row.get("execution_error") is not None]
    total_retrieved = sum(int(row["retrieved"]) for row in scored_rows)
    total_relevant = sum(int(row["relevant"]) for row in scored_rows)
    total_relevant_retrieved = sum(int(row["relevant_retrieved"]) for row in scored_rows)
    micro_precision = total_relevant_retrieved / total_retrieved if total_retrieved else 0.0
    micro_recall = total_relevant_retrieved / total_relevant if total_relevant else 0.0
    summary = {
        "gold_topics": len(topic_ids),
        "scored_topics": len(scored_rows),
        "coverage": len(scored_rows) / len(topic_ids),
        "validated_topics": len(validation_rows),
        "macro_precision": statistics.mean(row["precision"] for row in scored_rows) if scored_rows else None,
        "macro_recall": statistics.mean(row["recall"] for row in scored_rows) if scored_rows else None,
        "macro_f1": statistics.mean(row["f1"] for row in scored_rows) if scored_rows else None,
        "macro_f3": statistics.mean(row["f3"] for row in scored_rows) if scored_rows else None,
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": f_score(micro_precision, micro_recall, 1.0),
        "micro_f3": f_score(micro_precision, micro_recall, 3.0),
        "retrieved_pmids": total_retrieved,
        "relevant_pmids": total_relevant,
        "relevant_retrieved_pmids": total_relevant_retrieved,
        "missing_topics": missing_topics,
        "failed_topics": [row["topic"] for row in failed_rows],
    }
    sorted_rows = sorted(scored_rows, key=lambda row: float(row["f3"]), reverse=True)
    return {
        "summary": summary,
        "rows": sorted_rows,
        "validation": validation_rows,
        "failures": failed_rows,
    }


def write_json_report(report_path: Path, report: dict[str, object]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = report_path.with_suffix(report_path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    temporary_path.replace(report_path)


def load_completed_rows(report_path: Path) -> list[dict[str, object]]:
    if not report_path.exists():
        raise SystemExit(f"Cannot resume: report JSON does not exist: {report_path}")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        rows = report["rows"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise SystemExit(f"Cannot resume from invalid report JSON: {report_path}") from error
    if not isinstance(rows, list) or not all(isinstance(row, dict) and "topic" in row for row in rows):
        raise SystemExit(f"Cannot resume from report without topic rows: {report_path}")
    return rows


def render_metrics(report: dict[str, object], top_k: int) -> str:
    summary = report["summary"]
    rows = report["rows"]
    validation = report.get("validation", [])
    failures = report.get("failures", [])
    assert isinstance(summary, dict)
    assert isinstance(rows, list)
    lines = [
        "Task 2 query evaluation",
        "-----------------------",
        "Gold target: included PMIDs in the updated review.",
        f"Gold topics: {summary['gold_topics']}",
        f"Scored topics: {summary['scored_topics']}",
        f"Coverage: {summary['coverage']:.3f}",
    ]
    if summary["validated_topics"]:
        lines.append(f"Validated topics: {summary['validated_topics']}")
        if validation:
            lines.append("Validated query result counts:")
            for row in validation:
                lines.append(f"{row['topic']}: {row['reported_total_results']}")
    if summary["scored_topics"]:
        lines.extend(
            [
                f"Macro precision: {summary['macro_precision']:.3f}",
                f"Macro recall: {summary['macro_recall']:.3f}",
                f"Macro F1: {summary['macro_f1']:.3f}",
                f"Macro F3: {summary['macro_f3']:.3f}",
                f"Micro precision: {summary['micro_precision']:.3f}",
                f"Micro recall: {summary['micro_recall']:.3f}",
                f"Micro F1: {summary['micro_f1']:.3f}",
                f"Micro F3: {summary['micro_f3']:.3f}",
                f"Relevant PMIDs retrieved: {summary['relevant_retrieved_pmids']} / {summary['relevant_pmids']}",
                f"Retrieved PMIDs: {summary['retrieved_pmids']}",
            ]
        )
    if summary["missing_topics"]:
        lines.append("Missing predictions: " + ", ".join(summary["missing_topics"]))
    if summary["failed_topics"]:
        lines.append("Failed queries: " + ", ".join(summary["failed_topics"]))
    if failures:
        lines.append("Failure details:")
        for row in failures:
            lines.append(f"{row['topic']}: {row['execution_error']}")
    lines.extend(["", f"Top {min(top_k, len(rows))} F3 scores"])
    lines.append("topic\tprecision\trecall\tf1\tf3\trelevant_retrieved\trelevant\tretrieved")
    for row in rows[:top_k]:
        lines.append(
            f"{row['topic']}\t{row['precision']:.3f}\t{row['recall']:.3f}\t{row['f1']:.3f}"
            f"\t{row['f3']:.3f}\t{row['relevant_retrieved']}\t{row['relevant']}"
            f"\t{row['retrieved']}"
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
    parser = argparse.ArgumentParser(description="Execute and evaluate Task 2 Boolean-query submissions.")
    parser.add_argument("--predictions-tsv", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--topics-dir", type=Path, default=DEFAULT_TOPICS_DIR)
    parser.add_argument("--gold-topics-dir", type=Path, default=DEFAULT_GOLD_TOPICS_DIR)
    parser.add_argument("--qrels", type=Path, default=DEFAULT_QRELS)
    parser.add_argument("--orbit-api-base", default=DEFAULT_ORBIT_API_BASE)
    parser.add_argument("--resume", action="store_true", help="Resume from rows already saved in --report-json.")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Test whether each query executes in Orbit without retrieving all result pages.",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--metrics-out", type=Path, default=DEFAULT_METRICS_OUT)
    parser.add_argument("--report-json", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--prototext-out", type=Path, default=DEFAULT_PROTOTEXT_OUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    completed_rows = load_completed_rows(args.report_json) if args.resume else None
    report = evaluate(
        read_topic_ids(args.topics_dir),
        args.gold_topics_dir,
        load_predictions(args.predictions_tsv),
        load_included_qrels(args.qrels),
        args.orbit_api_base,
        checkpoint=lambda partial_report: write_json_report(args.report_json, partial_report),
        completed_rows=completed_rows,
        validate_only=args.validate_only,
    )
    metrics = render_metrics(report, max(1, args.top_k))
    args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_out.write_text(metrics, encoding="utf-8")
    write_json_report(args.report_json, report)
    args.prototext_out.parent.mkdir(parents=True, exist_ok=True)
    args.prototext_out.write_text(render_prototext(report), encoding="utf-8")
    print(metrics, end="")


if __name__ == "__main__":
    main()