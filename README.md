# UP2DATE: Shared Task on Systematic Review Updates

UP2DATE @ SCOLIA 2027 is a shared task on methods that assist with updating
systematic reviews. More information is available at
https://up2date.health-nlp.com/.

## Corrected release prepared on 2026-11-16

This branch prepares corrected data for evaluator image
`mam10eks/up2date-evaluator:0.0.4`. It does not confirm that the image has been
published or that TIRA has been updated. Organizers must verify deployment
before announcing this release as the live TIRA dataset.

Changes from the previous release:

- Labels now use verified included-study PMIDs, rather than all references.
  References without a mapped PMID are not scored against the PubMed collection.
- An initial protocol has no included-study labels.
- Topic files include `Stage` (`review` or `protocol`) and `Track` (`track_a`
  or `track_b`). Track A is a review-to-review update; Track B is a
  protocol-to-first-review pair.
- Task 1 no longer reports cutoff recall or uses `cutoff-gold.tsv`. It reports
  full-date and year accuracy, signed and absolute date error in days, and
  accuracy within 90 and 180 days of the gold date.
- Tasks 2 and 3 report precision, recall, F1 and F3. Task 2 targets included
  PMIDs in the updated review; Task 3 targets newly included studies, excluding
  studies already included initially. Task 3 topics with no new positives are
  excluded from macro scores but retained in micro scores.
- Evaluators report pooled scores and breakdowns by track and update type
  (`new_content` or `edit`). Update type is gold metadata, not a participant
  input. For an edit, the Task 1 gold date is the correction publication date,
  not necessarily the date of a new search.

Earlier scores for Tasks 2 and 3 are not comparable with this corrected release.
No primary ranking metric is newly designated by this release note.

## Data split and privacy

The 35 topics retain the fixed split in [topic-split.tsv](2026/topic-split.tsv):

- `2026/up2date-task-{1,2,3}-training/`: inputs and public truths for 20 topics.
- `2026/up2date-task-{1,2,3}-test/`: inputs only for 15 topics.
- `2026/up2date-task-{1,2,3}-spot-check/`: public two-topic checks with example
  answers. Both topics, `CD010216` (Track A) and `CD014160` (Track B), belong to
  training. No hidden test topic is used.
- [baselines](2026/baselines/): runnable prediction code.
- [evaluation](2026/evaluation/): offline scoring code.
- [baseline-output](2026/baseline-output/README.md): refreshed training and test
  submissions, without test scores.
- [training results](2026/evaluation-output/release-2026-11-16/training/README.md):
  local scores on public training truths only.
- [September archive](2026/evaluation-output/release-2026-09-07/training/README.md):
  historical training submissions and scores from the old data and metrics.

Hidden test truths, updated-review gold files, version-pair manifests and
per-topic gold metadata are not distributed for test topics. Full-set truth
packages also contain test answers and must not be copied here.

Tasks 2 and 3 include `inputs/initial-included-studies.tsv` for both training
and test. Its columns are `topic` and `pmids` (semicolon-separated), with one
row per topic. An empty value explicitly means no mapped initial included
studies; protocols always have an empty list. These initial-version PMIDs
are public input, not updated-review test answers. Participants may use them
to develop queries or screening methods; the existing baselines are unchanged.

Organizers upload inputs and hidden truths to TIRA from the private repository.
TIRA runs the evaluator image against stored truths and submitted predictions;
it does not synchronize dataset changes from this public repository.
All three evaluators are offline. Task 2 submissions contain both queries and
retrieved results, so evaluation never calls Orbit.

## Baselines

Run commands from the repository root with Python 3.10 or newer:

```bash
python3 -m pip install -r 2026/baselines/requirements.txt
```

The baseline methods are unchanged: initial date + 24 months (Task 1), execute
the initial query (Task 2), and predict every candidate as included (Task 3).
Task 2 generation calls the public Orbit API and may take several minutes.
Tasks 1 and 3 need no network access.

Choose `training`, `test`, or `spot-check` explicitly:

```bash
SPLIT=training

python3 2026/baselines/task_1.py \
  --topics-dir 2026/up2date-task-1-$SPLIT/inputs/topics \
  --output-tsv 2026/baseline-output/task-1-$SPLIT/predictions.tsv

python3 2026/baselines/task_2.py \
  --topics-dir 2026/up2date-task-2-$SPLIT/inputs/topics \
  --queries-tsv 2026/baseline-output/task-2-$SPLIT/queries.tsv \
  --run 2026/baseline-output/task-2-$SPLIT/run.txt.gz

python3 2026/baselines/task_3.py \
  --candidates-tsv 2026/up2date-task-3-$SPLIT/inputs/candidates.tsv \
  --output-tsv 2026/baseline-output/task-3-$SPLIT/predictions.tsv
```

Without path overrides, the scripts use the test inputs and test output paths.
For Task 2, archive `queries.tsv` and `run.txt.gz` together at the ZIP root.
The saved Task 2 submissions reuse the cached Orbit retrieval run with every
query checked against the current public inputs; see the output provenance.

## Local training evaluation and spot checks

After generating training predictions above, run:

```bash
SPLIT=training
OUT=2026/evaluation-output/local/$SPLIT
mkdir -p "$OUT"/task-{1,2,3}

python3 2026/evaluation/task_1.py \
  --predictions-tsv 2026/baseline-output/task-1-$SPLIT/predictions.tsv \
  --topics-dir 2026/up2date-task-1-$SPLIT/inputs/topics \
  --gold-topics-dir 2026/up2date-task-1-$SPLIT/truths/updated-review-topics \
  --metrics-out "$OUT/task-1/task1-evaluation.txt" \
  --report-json "$OUT/task-1/task1-evaluation.json" \
  --prototext-out "$OUT/task-1/evaluation.prototext"

python3 2026/evaluation/task_2.py \
  --queries-tsv 2026/baseline-output/task-2-$SPLIT/queries.tsv \
  --run 2026/baseline-output/task-2-$SPLIT/run.txt.gz \
  --topics-dir 2026/up2date-task-2-$SPLIT/inputs/topics \
  --gold-topics-dir 2026/up2date-task-2-$SPLIT/truths/updated-review-topics \
  --qrels 2026/up2date-task-2-$SPLIT/truths/included-studies-qrels.txt \
  --metrics-out "$OUT/task-2/task2-evaluation.txt" \
  --report-json "$OUT/task-2/task2-evaluation.json" \
  --prototext-out "$OUT/task-2/evaluation.prototext"

python3 2026/evaluation/task_3.py \
  --predictions-tsv 2026/baseline-output/task-3-$SPLIT/predictions.tsv \
  --candidates-tsv 2026/up2date-task-3-$SPLIT/inputs/candidates.tsv \
  --pair-manifest 2026/up2date-task-3-$SPLIT/truths/review-version-pairs.csv \
  --training-qrels 2026/up2date-task-3-$SPLIT/truths/initial-review-qrels.txt \
  --testing-qrels 2026/up2date-task-3-$SPLIT/truths/updated-review-qrels.txt \
  --metrics-out "$OUT/task-3/task3-evaluation.txt" \
  --report-json "$OUT/task-3/task3-evaluation.json" \
  --prototext-out "$OUT/task-3/evaluation.prototext"
```

These commands also work with `SPLIT=spot-check` after generating spot-check
baseline predictions. To validate the supplied perfect-answer examples instead,
replace each `2026/baseline-output/task-N-$SPLIT` submission path with
`2026/up2date-task-N-spot-check/example-submission`.
They are format/scoring examples, not outputs of the baseline methods.
Do not use these evaluation commands for `test`: its truths are private in TIRA.

