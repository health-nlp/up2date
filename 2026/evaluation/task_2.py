"""Evaluate Task 2 query-and-run submissions without external services.

The submission consists of a query TSV and a gzip-compressed six-column TREC
run. Queries are archived and checked for topic coverage but are not executed.
Retrieved PMIDs are read exclusively from the submitted run and compared with
the updated-review qrels.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import statistics
from collections import defaultdict
from pathlib import Path


DEFAULT_QUERIES = Path("baselines/task_2/queries.tsv")
DEFAULT_RUN = Path("baselines/task_2/run.txt.gz")
DEFAULT_GOLD_TOPICS_DIR = Path("datasets-for-tira/up2date-task-2/truths/updated-review-topics")
DEFAULT_QRELS = Path("datasets-for-tira/up2date-task-2/truths/included-studies-qrels.txt")
DEFAULT_METRICS_OUT = Path("baselines/task_2/eval/task2_eval_metrics.txt")
DEFAULT_REPORT_JSON = Path("baselines/task_2/eval/task2_eval_report.json")
DEFAULT_PROTOTEXT_OUT = Path("baselines/task_2/eval/evaluation.prototext")

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


def load_queries(queries_tsv: Path) -> dict[str, str]:
    if not queries_tsv.exists():
        raise SystemExit(f"Queries file does not exist: {queries_tsv}")
    queries: dict[str, str] = {}
    with queries_tsv.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, delimiter="\t")
        if set(("topic", "query")) - set(reader.fieldnames or []):
            raise SystemExit("Queries TSV must contain 'topic' and 'query' columns.")
        for line_number, row in enumerate(reader, start=2):
            topic = (row.get("topic") or "").strip()
            query = (row.get("query") or "").strip()
            if not topic or not query:
                raise SystemExit(f"Empty topic or query in {queries_tsv}:{line_number}")
            if topic in queries:
                raise SystemExit(f"Duplicate query topic {topic!r} in {queries_tsv}:{line_number}")
            queries[topic] = query
    return queries


def load_run(run_path: Path) -> dict[str, set[str]]:
    if not run_path.exists():
        raise SystemExit(f"Run file does not exist: {run_path}")
    if run_path.suffix != ".gz":
        raise SystemExit(f"Run file must be gzip-compressed and end in .gz: {run_path}")

    retrieved: dict[str, set[str]] = defaultdict(set)
    seen_topic_pmids: set[tuple[str, str]] = set()
    seen_topic_ranks: set[tuple[str, int]] = set()
    try:
        with gzip.open(run_path, "rt", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                fields = line.split()
                if len(fields) != 6:
                    raise SystemExit(
                        f"Expected six TREC run columns in {run_path}:{line_number}"
                    )
                topic, iteration, pmid, rank_text, score_text, run_tag = fields
                if iteration != "Q0":
                    raise SystemExit(f"Expected Q0 in {run_path}:{line_number}")
                if not pmid.isdigit():
                    raise SystemExit(f"PMID must be numeric in {run_path}:{line_number}")
                try:
                    rank = int(rank_text)
                    float(score_text)
                except ValueError as error:
                    raise SystemExit(f"Invalid rank or score in {run_path}:{line_number}") from error
                if rank < 1 or not run_tag:
                    raise SystemExit(f"Invalid rank or run tag in {run_path}:{line_number}")
                if (topic, pmid) in seen_topic_pmids:
                    raise SystemExit(f"Duplicate PMID for topic {topic!r} in {run_path}:{line_number}")
                if (topic, rank) in seen_topic_ranks:
                    raise SystemExit(f"Duplicate rank for topic {topic!r} in {run_path}:{line_number}")
                seen_topic_pmids.add((topic, pmid))
                seen_topic_ranks.add((topic, rank))
                retrieved[topic].add(pmid)
    except (gzip.BadGzipFile, EOFError, UnicodeDecodeError) as error:
        raise SystemExit(f"Cannot read gzip TREC run {run_path}: {error}") from error
    return dict(retrieved)


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


def evaluate(
    topic_ids: list[str],
    gold_topics_dir: Path,
    queries: dict[str, str],
    run: dict[str, set[str]],
    qrels: dict[str, set[str]],
) -> dict[str, object]:
    expected_topics = set(topic_ids)
    missing_query_topics = sorted(expected_topics - set(queries))
    if missing_query_topics:
        raise SystemExit("Queries are missing topics: " + ", ".join(missing_query_topics))
    topics_without_results = sorted(expected_topics - set(run))
    rows: list[dict[str, object]] = []
    for topic in topic_ids:
        version = read_topic_version(resolve_topic_path(gold_topics_dir, topic))
        relevant = qrels.get(f"{topic}_{version}", set())
        retrieved = run.get(topic, set())
        relevant_retrieved = relevant & retrieved
        precision = len(relevant_retrieved) / len(retrieved) if retrieved else 0.0
        recall = len(relevant_retrieved) / len(relevant) if relevant else 0.0
        rows.append(
            {
                "topic": topic,
                "updated_version": version,
                "query": queries.get(topic),
                "retrieved": len(retrieved),
                "relevant": len(relevant),
                "relevant_retrieved": len(relevant_retrieved),
                "precision": precision,
                "recall": recall,
                "f1": f_score(precision, recall, 1.0),
                "f3": f_score(precision, recall, 3.0),
            }
        )

    total_retrieved = sum(int(row["retrieved"]) for row in rows)
    total_relevant = sum(int(row["relevant"]) for row in rows)
    total_relevant_retrieved = sum(int(row["relevant_retrieved"]) for row in rows)
    micro_precision = total_relevant_retrieved / total_retrieved if total_retrieved else 0.0
    micro_recall = total_relevant_retrieved / total_relevant if total_relevant else 0.0
    summary = {
        "gold_topics": len(topic_ids),
        "scored_topics": len(rows),
        "coverage": 1.0,
        "query_coverage": 1.0,
        "macro_precision": statistics.mean(float(row["precision"]) for row in rows),
        "macro_recall": statistics.mean(float(row["recall"]) for row in rows),
        "macro_f1": statistics.mean(float(row["f1"]) for row in rows),
        "macro_f3": statistics.mean(float(row["f3"]) for row in rows),
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": f_score(micro_precision, micro_recall, 1.0),
        "micro_f3": f_score(micro_precision, micro_recall, 3.0),
        "retrieved_pmids": total_retrieved,
        "relevant_pmids": total_relevant,
        "relevant_retrieved_pmids": total_relevant_retrieved,
        "topics_without_results": topics_without_results,
    }
    return {
        "summary": summary,
        "rows": sorted(rows, key=lambda row: float(row["f3"]), reverse=True),
    }


def write_json_report(report_path: Path, report: dict[str, object]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def render_metrics(report: dict[str, object], top_k: int) -> str:
    summary = report["summary"]
    rows = report["rows"]
    assert isinstance(summary, dict)
    assert isinstance(rows, list)
    lines = [
        "Task 2 retrieval-run evaluation",
        "-------------------------------",
        "Gold target: included PMIDs in the updated review.",
        "Retrieval source: submitted TREC run (offline evaluation).",
        f"Gold topics: {summary['gold_topics']}",
        f"Scored topics: {summary['scored_topics']}",
        f"Run coverage: {summary['coverage']:.3f}",
        f"Query coverage: {summary['query_coverage']:.3f}",
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
    if summary["topics_without_results"]:
        lines.append(
            "Topics with zero retrieved PMIDs: " + ", ".join(summary["topics_without_results"])
        )
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
        if not isinstance(value, (int, float)):
            raise ValueError(f"Metric {metric_name} is not numeric: {value!r}")
        blocks.append(f'measure{{\n  key: "{display_name}"\n  value: "{value}"\n}}')
    return "\n".join(blocks) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a Task 2 query and TREC-run submission offline.")
    parser.add_argument("--queries-tsv", type=Path, default=DEFAULT_QUERIES)
    parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
    parser.add_argument("--gold-topics-dir", type=Path, default=DEFAULT_GOLD_TOPICS_DIR)
    parser.add_argument("--qrels", type=Path, default=DEFAULT_QRELS)
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
        load_queries(args.queries_tsv),
        load_run(args.run),
        load_included_qrels(args.qrels),
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