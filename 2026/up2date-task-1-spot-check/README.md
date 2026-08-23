---
configs:
- config_name: inputs
  data_files:
  - split: test
    path: "inputs/topics/*"
- config_name: truths
  data_files:
  - split: test
    path:
    - "truths/updated-review-topics/*"
    - "truths/cutoff-gold.tsv"

tira_configs:
  resolve_inputs_to: "inputs"
  resolve_truths_to: "truths"
  default_upload_name: "predictions.tsv"

  input_format:
    name: "arbitrary"
  truth_format:
    name: "arbitrary"

  baseline:
    link: "../baselines"
    command: >-
      python3 /task_1.py
      --topics-dir $inputDataset/topics
      --output-tsv $outputDir/predictions.tsv
    format:
      name: "*.tsv"

  evaluator:
    image: "mam10eks/up2date-evaluator:0.0.1"
    command: >-
      python3 /task_1.py
      --predictions-tsv ${inputRun}/predictions.tsv
      --gold-topics-dir ${inputDataset}/updated-review-topics
      --cutoff-gold-tsv ${inputDataset}/cutoff-gold.tsv
      --metrics-out ${outputDir}/task1-evaluation.txt
      --report-json ${outputDir}/task1-evaluation.json
      --prototext-out ${outputDir}/evaluation.prototext
---

# Up2Date Task 1 Spot-Check Package

The `inputs/` and public `truths/` contain the 3 development topics listed from the training set to ensure that approaches work.

## Task

Task 1 asks systems to predict the publication date of the next update of a systematic review.

## System input

The `topics/` directory contains one initial-review `.txt` topic file per
review. Each file is named with its topic identifier and contains fields such
as `Topic`, `Version`, `Title`, `Year`, `Date`, and `Abstract`.

## Submission format

Submit one tab-separated file named `predictions.tsv` with the columns `topic`
and `date`. Each topic must occur once, and dates must use ISO `YYYY-MM-DD`
format.

## Private truth data

The evaluator receives:

- `updated-review-topics/`, containing the gold updated review dates; and
- `cutoff-gold.tsv`, containing the columns `topic`, `pmid`, and
  `publication_year` for offline cutoff-recall evaluation.

Evaluation reports topic coverage, full-date and year accuracy, signed and
absolute date error in days, and macro and micro recall of newly relevant
studies covered by the predicted cutoff year.

The input and truth configurations are separate so participant systems cannot
access updated review dates or cutoff-recall labels.

## Local validation

From the repository root:

```bash
tira-cli dataset-submission \
  --path up2date-task-1-spot-check \
  --task up2date \
  --split test \
  --dry-run
```

Remove `--dry-run` to upload to TIRA.
