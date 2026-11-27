# UP2DATE Task 3 Spot Check

Public validation dataset containing the topics `CD010216` and `CD014160`.

- `inputs/` mirrors the participant-facing dataset.
- `truths/` mirrors the evaluator-facing dataset.
- `example-submission/predictions.tsv` is a valid submission for local validation.

## Initially included studies

`inputs/initial-included-studies.tsv` is participant input, including for test
topics. It has columns `topic` and `pmids`, with one row per topic and a
semicolon-separated list of PMIDs included in the initial version. An empty
`pmids` value explicitly means no mapped initial included studies; protocols
always have an empty list. References without a mapped PMID are not listed.
These are not updated-review labels or predictions. Updated-review test labels
remain private. The baseline methods do not use this optional extra information.
