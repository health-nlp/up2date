# UP2DATE: Shared Task on Systematic Review Updates

UP2DATE @ SCOLIA 2027 is a shared task on methods that assist with updating
systematic reviews. More information is available at
https://up2date.health-nlp.com/.

## 2026 Data Split

The 35 topics use one fixed split recorded in `2026/topic-split.tsv`:

- `up2date-task-{1,2,3}-training/`: inputs and public truths for 20 development
	topics;
- `up2date-task-{1,2,3}-test/`: inputs for the remaining 15 topics, with their
	truths held privately in TIRA;
- `baselines/`: simple runnable baseline scripts for the current formats.

The 15 test `truths/` remain private and are available only to the TIRA
evaluators until the submission deadline.

## Baselines

Run the baselines from the repository root with Python 3.10 or newer:

```bash
python3 -m pip install -r 2026/baselines/requirements.txt
```

```bash
python3 2026/baselines/task_1.py
python3 2026/baselines/task_2.py
python3 2026/baselines/task_3.py
```

By default, these commands run on the 20-topic training inputs and write
training submissions to `2026/baseline-output/`. The public truths score these
20 development topics; TIRA scores separate submissions for the remaining 15
topics privately.
Task 2 executes the topic queries
through the public Orbit API, so it requires network access and may take
several minutes. Tasks 1 and 3 run locally.

To produce submissions for the 15-topic test packages, override the paths:

```bash
python3 2026/baselines/task_1.py \
	--topics-dir 2026/up2date-task-1-test/inputs/topics \
	--output-tsv 2026/baseline-output/task-1-test/predictions.tsv

python3 2026/baselines/task_2.py \
	--topics-dir 2026/up2date-task-2-test/inputs/topics \
	--queries-tsv 2026/baseline-output/task-2-test/queries.tsv \
	--run 2026/baseline-output/task-2-test/run.txt.gz

python3 2026/baselines/task_3.py \
	--candidates-tsv 2026/up2date-task-3-test/inputs/candidates.tsv \
	--output-tsv 2026/baseline-output/task-3-test/predictions.tsv
```

