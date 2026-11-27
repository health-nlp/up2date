# UP2DATE Task 2 Test Inputs

This package contains participant inputs for the 15 `test` topics in
`../topic-split.tsv`. No test truths or test evaluation scores are published.
Submit predictions to TIRA; use the corresponding training package for local evaluation.

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

## Hidden test truth data

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

The truths described here are held privately in TIRA and are not part of this package.

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
