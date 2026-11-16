# UP2DATE Task 3 Test Inputs

This package contains participant inputs for the 15 `test` topics in
`../topic-split.tsv`. No test truths or test evaluation scores are published.
Submit predictions to TIRA; use the corresponding training package for local evaluation.

Task 3 asks systems to identify which candidate studies were newly included in
an updated systematic review.

## System input

`candidates.tsv` is a tab-separated file with the columns `topic` and `study`. Each row identifies one candidate PubMed study for a review topic. The file contains no relevance labels.

## Submission format

Submit one file named `predictions.tsv` with the same `topic` and `study` columns. Each row predicts that the study was included in the updated review. Candidates omitted from the submission are predicted as excluded.

## Hidden test truth data

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

The labels described here are held privately in TIRA and are not distributed
in this repository.

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
