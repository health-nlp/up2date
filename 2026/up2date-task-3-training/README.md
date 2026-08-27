---
configs:
- config_name: inputs
  data_files:
  - split: test
    path: "inputs/candidates.tsv"
- config_name: truths
  data_files:
  - split: test
    path:
    - "truths/review-version-pairs.csv"
    - "truths/initial-review-qrels.txt"
    - "truths/updated-review-qrels.txt"

tira_configs:
  resolve_inputs_to: "inputs"
  resolve_truths_to: "truths"
  default_upload_name: "predictions.tsv"

  input_format:
    name: "*.tsv"
  truth_format:
    name: "arbitrary"

  baseline:
    link: "../../src/baselines"
    command: >-
      python3 /baseline_task_3.py
      --candidates-tsv $inputDataset/candidates.tsv
      --output-tsv $outputDir/predictions.tsv
    format:
      name: "*.tsv"

  evaluator:
    image: "mam10eks/up2date-evaluator:0.0.1"
    command: >-
      python3 /task_3.py
      --predictions-tsv ${inputRun}/predictions.tsv
      --pair-manifest ${inputDataset}/review-version-pairs.csv
      --training-qrels ${inputDataset}/initial-review-qrels.txt
      --testing-qrels ${inputDataset}/updated-review-qrels.txt
      --metrics-out ${outputDir}/task3-evaluation.txt
      --report-json ${outputDir}/task3-evaluation.json
      --prototext-out ${outputDir}/evaluation.prototext
---

# Up2Date Task 3 Training Package

The `inputs/` and public `truths/` contain the 20 development topics listed as
`training` in `../topic-split.tsv`.

## Task

Task 3 asks systems to identify which candidate studies were newly included in
an updated systematic review.

## System input

`candidates.tsv` is a tab-separated file with the columns `topic` and `study`. Each row identifies one candidate PubMed study for a review topic. The file contains no relevance labels.

## Submission format

Submit one file named `predictions.tsv` with the same `topic` and `study` columns. Each row predicts that the study was included in the updated review. Candidates omitted from the submission are predicted as excluded.

## Private truth data

The evaluator receives:

- `review-version-pairs.csv`, which maps each topic to its initial and updated
  review versions;
- `initial-review-qrels.txt`, containing candidate labels for the initial
  review; and
- `updated-review-qrels.txt`, containing candidate labels for the updated
  review.

The qrels use the four-column TREC format
`topic_version 0 study relevance`. Evaluation removes studies already included
in the initial review and reports precision, recall, F1, and recall-oriented F3
for newly included studies. Topics with no newly included studies are excluded
from macro metrics, counted separately, and retained in micro metrics.

The dataset is generated directly from the review extraction outputs by the
scripts in `src/export/`. The input and truth configurations are deliberately
separate so participant systems cannot access labels.

## Local packaging validation

From the repository root:

```bash
tira-cli dataset-submission \
  --path datasets-for-tira/up2date-task-3 \
  --task up2date \
  --split test \
  --dry-run
```

Remove the `--dry-run` to upload to TIRA.
