"""Build a simple Task 1 review-update date baseline.

INPUT
	--topics-dir
			Initial review topic files. Uses each file's Date field when available.

METHOD
	- Adds --lag-months to the topic publication date (default: 24 months).
	- If no valid Date is available, predicts 1 January after --fallback-years.
	- Ensures the predicted date is later than the initial review date.

OUTPUT
	--output-tsv
			TSV columns: topic, date. Dates use YYYY-MM-DD format.

RUN
	python3 2026/baselines/task_1.py
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
from pathlib import Path


DEFAULT_TOPICS_DIR = Path("2026/up2date-task-1-test/inputs/topics")
DEFAULT_OUTPUT_TSV = Path("2026/baseline-output/task-1-test/predictions.tsv")

MONTHS_EN = {
	"january": 1,
	"february": 2,
	"march": 3,
	"april": 4,
	"may": 5,
	"june": 6,
	"july": 7,
	"august": 8,
	"september": 9,
	"october": 10,
	"november": 11,
	"december": 12,
}

SEARCH_DATE_PATTERNS = [
	# Example: "latest search date was 25 August 2023"
	re.compile(
		r"(?:latest\s+search\s+date\s+was|date\s+of\s+the\s+last\s+search\s+was|last\s+search\s+was)"
		r"\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})",
		flags=re.IGNORECASE,
	),
	# Example: "to 1 February 2024" in search methods lines
	re.compile(
		r"\bto\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b",
		flags=re.IGNORECASE,
	),
]

DATE_RE = re.compile(r"^Date:\s*(\d{4})-(\d{2})-(\d{2})\s*$", flags=re.IGNORECASE)
YEAR_RE = re.compile(r"^Year:\s*(\d{4})\s*$", flags=re.IGNORECASE)


def add_months(date_value: dt.date, months: int) -> dt.date:
	year = date_value.year + (date_value.month - 1 + months) // 12
	month = (date_value.month - 1 + months) % 12 + 1

	if month == 12:
		next_month = dt.date(year + 1, 1, 1)
	else:
		next_month = dt.date(year, month + 1, 1)
	last_day = (next_month - dt.timedelta(days=1)).day
	day = min(date_value.day, last_day)
	return dt.date(year, month, day)


def parse_topic_file(topic_path: Path) -> tuple[str, str, str, str]:
	topic_id = topic_path.stem
	publish_date = ""
	year = ""
	text = topic_path.read_text(encoding="utf-8", errors="replace")

	for line in text.splitlines():
		date_match = DATE_RE.match(line.strip())
		if date_match:
			year_str, month_str, day_str = date_match.groups()
			publish_date = f"{year_str}-{month_str}-{day_str}"
			continue

		year_match = YEAR_RE.match(line.strip())
		if year_match:
			year = year_match.group(1)
			continue

	return topic_id, publish_date, year, text


def extract_search_date(text: str) -> dt.date | None:
	for pattern in SEARCH_DATE_PATTERNS:
		match = pattern.search(text)
		if not match:
			continue

		day_str, month_str, year_str = match.groups()
		month = MONTHS_EN.get(month_str.lower())
		if month is None:
			continue

		try:
			return dt.date(int(year_str), month, int(day_str))
		except ValueError:
			continue

	return None


def predict_date(
	topic_text: str,
	publish_date: str,
	year_value: str,
	lag_months: int,
	fallback_years: int,
) -> dt.date:
	base_date: dt.date | None = None
	if publish_date:
		try:
			base_date = dt.date.fromisoformat(publish_date)
		except ValueError:
			base_date = None

	base_year: int | None = None
	try:
		base_year = int(year_value)
	except (TypeError, ValueError):
		base_year = None

	if base_date is not None:
		predicted = add_months(base_date, lag_months)
	elif base_year is None:
		# Conservative fixed fallback if topic format is unexpected.
		predicted = dt.date(2030, 1, 1)
	else:
		predicted = dt.date(base_year + fallback_years, 1, 1)

	# Enforce "update date > original review date".
	if base_date is not None and predicted <= base_date:
		predicted = base_date + dt.timedelta(days=1)
	elif base_year is not None:
		min_allowed = dt.date(base_year + 1, 1, 1)
		if predicted < min_allowed:
			predicted = min_allowed

	return predicted


def build_predictions(
	topics_dir: Path,
	lag_months: int,
	fallback_years: int,
) -> list[tuple[str, str]]:
	rows: list[tuple[str, str]] = []

	topic_files = sorted(p for p in topics_dir.iterdir() if p.is_file())
	if not topic_files:
		raise SystemExit(f"No topic files found in: {topics_dir}")

	for topic_path in topic_files:
		topic_id, publish_date, year_value, topic_text = parse_topic_file(topic_path)
		pred = predict_date(
			topic_text=topic_text,
			publish_date=publish_date,
			year_value=year_value,
			lag_months=lag_months,
			fallback_years=fallback_years,
		)
		rows.append((topic_id, pred.isoformat()))

	return rows


def write_tsv(output_path: Path, rows: list[tuple[str, str]]) -> None:
	output_path.parent.mkdir(parents=True, exist_ok=True)
	with output_path.open("w", encoding="utf-8", newline="") as f:
		writer = csv.writer(f, delimiter="\t")
		writer.writerow(["topic", "date"])
		writer.writerows(rows)


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Build a demo Task 1 baseline TSV.")
	parser.add_argument(
		"--topics-dir",
		type=Path,
		default=DEFAULT_TOPICS_DIR,
		help="Directory containing participant-available topic files.",
	)
	parser.add_argument(
		"--output-tsv",
		type=Path,
		default=DEFAULT_OUTPUT_TSV,
		help="Output TSV path with columns: topic, date.",
	)
	parser.add_argument(
		"--lag-months",
		type=int,
		default=24,
		help="Months added to extracted search date.",
	)
	parser.add_argument(
		"--fallback-years",
		type=int,
		default=2,
		help="Years added to topic Year when no search date is found.",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	rows = build_predictions(
		topics_dir=args.topics_dir,
		lag_months=args.lag_months,
		fallback_years=args.fallback_years,
	)
	write_tsv(args.output_tsv, rows)
	print(f"Wrote {len(rows)} Task 1 predictions to: {args.output_tsv}")


if __name__ == "__main__":
	main()
