---
configs:
- config_name: inputs
  data_files:
  - split: test
    path:
    - "inputs/candidates.tsv"
    - "inputs/initial-included-studies.tsv"
- config_name: truths
  data_files:
  - split: test
    path:
    - "truths/review-version-pairs.csv"
    - "truths/initial-review-qrels.txt"
    - "truths/updated-review-qrels.txt"
    - "inputs/candidates.tsv"

tira_configs:
  resolve_inputs_to: "inputs"
  resolve_truths_to: "."
  default_upload_name: "predictions.tsv"

  input_format:
    name: "arbitrary"
  truth_format:
    name: "arbitrary"

  baseline:
    link: "../baselines"
    command: >-
      python3 /task_3.py
      --candidates-tsv $inputDataset/candidates.tsv
      --output-tsv $outputDir/predictions.tsv
    format:
      name: "*.tsv"

  evaluator:
    image: "mam10eks/up2date-evaluator:0.0.4"
    command: >-
      python3 /task_3.py
      --predictions-tsv ${inputRun}/predictions.tsv
      --pair-manifest ${inputDataset}/truths/review-version-pairs.csv
      --training-qrels ${inputDataset}/truths/initial-review-qrels.txt
      --testing-qrels ${inputDataset}/truths/updated-review-qrels.txt
      --candidates-tsv ${inputDataset}/inputs/candidates.tsv
      --metrics-out ${outputDir}/task3-evaluation.txt
      --report-json ${outputDir}/task3-evaluation.json
      --prototext-out ${outputDir}/evaluation.prototext
---

# Up2Date Task 3: New Study Inclusion

Task 3 asks systems to identify which candidate studies were newly included in
an updated systematic review.

## System input

`candidates.tsv` is a tab-separated file with the columns `topic` and `study`. Each row identifies one candidate PubMed study for a review topic. The file contains no relevance labels.

## Submission format

Submit one file named `predictions.tsv` with the same `topic` and `study` columns. Each row predicts that the study was included in the updated review. Candidates omitted from the submission are predicted as excluded.

## Public training truth data

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

These public training labels are generated from verified included-study PMIDs.
The input and truth configurations are separate; hidden test labels are not
distributed in this repository.

## Initially included studies

`inputs/initial-included-studies.tsv` is participant input, including for test
topics. It has columns `topic` and `pmids`, with one row per topic and a
semicolon-separated list of PMIDs included in the initial version. An empty
`pmids` value explicitly means no mapped initial included studies; protocols
always have an empty list. References without a mapped PMID are not listed.
These are not updated-review labels or predictions. Updated-review test labels
remain private. The baseline methods do not use this optional extra information.

## Reporting by track and update type

Every topic belongs to one of two tracks, and every pair has an update type:

- Track A: the initial version is a completed review and the updated version is
  an update of it (9 of 35 topics). Track B: the initial version is a protocol
  and the updated version is the first review (26 of 35 topics).
- Update type `new_content`: Cochrane marks the updated version as a new review
  or a new search for studies. Update type `edit`: it marks it as an edit of an
  existing version. Participants see `Stage` and `Track` in the topic files, but
  not the update type.

Only studies with a PubMed ID count as included studies.

Scores are reported for all topics together and also for each track and each
update type. A group with no topic that has a new included study shows `n/a` for
the macro scores. Protocols have no included studies, so Track B topics have no
initial labels.

## Local packaging validation

From the repository root:

```bash
tira-cli dataset-submission \
  --path 2026/up2date-task-3-training \
  --task up2date \
  --split test \
  --dry-run
```

This command validates the public training package locally. Hidden test
packages are uploaded separately by the organizers from the private repository.
