"""Build a Task 2 query-and-run baseline from the initial review queries.

INPUT
	--topics-dir
			Initial review topic files containing a QueryOrbit field.

METHOD
	Copies each QueryOrbit value verbatim. QueryOrbit is the topic file's
	executable Orbit form of the initial review's Boolean query. The baseline
	executes each query through Orbit and stores all retrieved PMIDs in a TREC run.

OUTPUT
	--queries-tsv
			TSV columns: topic, query.
	--run
			Gzip-compressed TREC run columns: topic, Q0, pmid, rank, score, run tag.

RUN
	python3 2026/baselines/task_2.py
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import socket
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_TOPICS_DIR = Path("2026/up2date-task-2-test/inputs/topics")
DEFAULT_QUERIES_TSV = Path("2026/baseline-output/task-2-test/queries.tsv")
DEFAULT_RUN = Path("2026/baseline-output/task-2-test/run.txt.gz")
DEFAULT_ORBIT_API_BASE = "https://orbit-api.health-nlp.com"
PAGE_SIZE = 1000
REQUEST_TIMEOUT_SECONDS = 60
REQUEST_INTERVAL_SECONDS = 0.2
MAX_RETRIES = 5
RUN_TAG = "initial-query-baseline"


def extract_query_orbit(topic_path: Path) -> str:
	lines = topic_path.read_text(encoding="utf-8", errors="replace").splitlines()
	for index, line in enumerate(lines):
		if line.strip() != "QueryOrbit:":
			continue
		query = "\n".join(lines[index + 1 :]).strip()
		if query:
			return query
		break
	raise SystemExit(f"No non-empty QueryOrbit field found in: {topic_path}")


def build_rows(topics_dir: Path) -> list[tuple[str, str]]:
	if not topics_dir.exists():
		raise SystemExit(f"Topics directory does not exist: {topics_dir}")

	topic_files = sorted(path for path in topics_dir.iterdir() if path.is_file())
	if not topic_files:
		raise SystemExit(f"No topic files found in: {topics_dir}")

	return [(topic_path.stem, extract_query_orbit(topic_path)) for topic_path in topic_files]


def write_tsv(output_path: Path, rows: list[tuple[str, str]]) -> None:
	output_path.parent.mkdir(parents=True, exist_ok=True)
	with output_path.open("w", encoding="utf-8", newline="") as file:
		writer = csv.writer(file, delimiter="\t")
		writer.writerow(["topic", "query"])
		writer.writerows(rows)


def fetch_json(api_base: str, params: dict[str, Any]) -> dict[str, Any]:
	url = f"{api_base.rstrip('/')}/entrez/eutils/esearch.fcgi?{urlencode(params)}"
	request = Request(url, headers={"Accept": "application/json", "User-Agent": "up2date-task2-baseline/1.0"})
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


def run_query(api_base: str, query: str) -> list[str]:
	retrieved: list[str] = []
	seen: set[str] = set()
	retstart = 0
	while True:
		payload = fetch_json(
			api_base,
			{"term": query, "retmode": "json", "retmax": PAGE_SIZE, "retstart": retstart},
		)
		search_result = payload.get("esearchresult") or payload.get("esearch") or {}
		batch_ids = [str(pmid) for pmid in (search_result.get("idlist") or [])]
		if not batch_ids:
			break
		for pmid in batch_ids:
			if pmid not in seen:
				seen.add(pmid)
				retrieved.append(pmid)
		retstart += len(batch_ids)
		if len(batch_ids) < PAGE_SIZE:
			break
	return retrieved


def write_run(run_path: Path, rows: list[tuple[str, str]], api_base: str) -> int:
	run_path.parent.mkdir(parents=True, exist_ok=True)
	total = 0
	with gzip.open(run_path, "wt", encoding="utf-8", newline="") as file:
		for topic, query in rows:
			print(f"Executing Task 2 baseline query: {topic}", flush=True)
			for rank, pmid in enumerate(run_query(api_base, query), start=1):
				file.write(f"{topic} Q0 {pmid} {rank} {1.0 / rank:.12g} {RUN_TAG}\n")
				total += 1
	return total


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Build the Task 2 initial-query baseline submission.")
	parser.add_argument("--topics-dir", type=Path, default=DEFAULT_TOPICS_DIR)
	parser.add_argument("--queries-tsv", type=Path, default=DEFAULT_QUERIES_TSV)
	parser.add_argument("--run", type=Path, default=DEFAULT_RUN)
	parser.add_argument("--orbit-api-base", default=DEFAULT_ORBIT_API_BASE)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	raise ValeuError("dsaad")
	rows = build_rows(args.topics_dir)
	write_tsv(args.queries_tsv, rows)
	run_rows = write_run(args.run, rows, args.orbit_api_base)
	print(f"Wrote {len(rows)} Task 2 baseline queries to: {args.queries_tsv}")
	print(f"Wrote {run_rows} Task 2 run rows to: {args.run}")


if __name__ == "__main__":
	main()
