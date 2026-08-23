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
    - "truths/included-studies-qrels.txt"

tira_configs:
  resolve_inputs_to: "inputs"
  resolve_truths_to: "truths"
  default_upload_name: "task2-submission"

  input_format:
    name: "arbitrary"
  truth_format:
    name: "arbitrary"

  baseline:
    link: "../baselines"
    command: >-
      python3 /baseline_task_2.py
      --topics-dir $inputDataset/topics
      --queries-tsv $outputDir/queries.tsv
      --run $outputDir/run.txt.gz
      --orbit-api-base $ORBIT_API_BASE
    format:
      name: "arbitrary"

  evaluator:
    image: "mam10eks/up2date-evaluator:0.0.1"
    allow_network: false
    command: >-
      python3 /task_2.py
      --queries-tsv ${inputRun}/queries.tsv
      --run ${inputRun}/run.txt.gz
      --gold-topics-dir ${inputDataset}/updated-review-topics
      --qrels ${inputDataset}/included-studies-qrels.txt
      --metrics-out ${outputDir}/task2-evaluation.txt
      --report-json ${outputDir}/task2-evaluation.json
      --prototext-out ${outputDir}/evaluation.prototext
---

# Up2Date Task 2 Spot-Check Package

The `inputs/` and public `truths/` contain the 4 development topics.

## Task

Task 2 asks systems to formulate an executable Boolean query for retrieving
studies relevant to the updated systematic review.

## System input

The `topics/` directory contains one initial-review `.txt` topic file per
review. Each file is named with its topic identifier and includes the review
metadata, abstract, and executable initial `QueryOrbit` query.

## Submission format

Submit one directory containing both of these files:

- `queries.tsv`: tab-separated columns `topic` and `query`, with every topic
  occurring exactly once;
- `run.txt.gz`: a gzip-compressed six-column TREC run with
  `topic Q0 pmid rank score run_tag`.

Participants execute each submitted query using their retrieval environment
and include every retrieved PMID in the run. The two files are archived
together as the complete Task 2 result.

## Private truth data

The evaluator receives:

- `updated-review-topics/`, whose `Version` fields select the updated-review
  qrels; and
- `included-studies-qrels.txt`, containing included PMIDs in four-column TREC
  qrels format.

The evaluator does not execute queries and makes no network requests. It reads
retrieved PMIDs from `run.txt.gz`, validates the TREC format and topic coverage,
and reports precision, recall, F1, and recall-oriented F3 per topic plus macro
and micro aggregates. `queries.tsv` is retained for provenance and future
reproducibility checks.

The input and truth configurations are separate so participant systems cannot
access updated review versions or included-study labels.

## Local validation

From the repository root:

```bash
tira-cli dataset-submission \
  --path up2date-task-2-spot-check \
  --task up2date \
  --split test \
  --dry-run
```

Remove `--dry-run` to upload to TIRA.
