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
    - "inputs/topics/*"

tira_configs:
  resolve_inputs_to: "inputs"
  resolve_truths_to: "."
  default_upload_name: "task2-submission"

  input_format:
    name: "arbitrary"
  truth_format:
    name: "arbitrary"

  baseline:
    link: "../baselines"
    allow_network: true
    command: >-
      python3 /task_2.py
      --topics-dir $inputDataset/topics
      --queries-tsv $outputDir/queries.tsv
      --run $outputDir/run.txt.gz
    format:
      name: "run.txt"

  evaluator:
    image: "mam10eks/up2date-evaluator:0.0.4"
    allow_network: false
    command: >-
      python3 /task_2.py
      --queries-tsv ${inputRun}/queries.tsv
      --run ${inputRun}/run.txt.gz
      --gold-topics-dir ${inputDataset}/truths/updated-review-topics
      --qrels ${inputDataset}/truths/included-studies-qrels.txt
      --topics-dir ${inputDataset}/inputs/topics
      --metrics-out ${outputDir}/task2-evaluation.txt
      --report-json ${outputDir}/task2-evaluation.json
      --prototext-out ${outputDir}/evaluation.prototext
---

# Up2Date Task 2: Updated Boolean Query Formulation

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

## Public training truth data

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

Training truths are public for development. Test truths remain private in TIRA.

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

## Local validation

From the repository root:

```bash
ORBIT_API_BASE="https://orbit-api.health-nlp.com" tira-cli dataset-submission \
  --path 2026/up2date-task-2-training \
  --task up2date \
  --split test \
  --forward-environment-variable ORBIT_API_BASE \
  --dry-run
```

This command validates the public training package locally. Hidden test
packages are uploaded separately by the organizers from the private repository.
