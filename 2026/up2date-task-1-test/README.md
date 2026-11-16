# UP2DATE Task 1 Test Inputs

This package contains participant inputs for the 15 `test` topics in
`../topic-split.tsv`. No test truths or test evaluation scores are published.
Submit predictions to TIRA; use the corresponding training package for local evaluation.

Task 1 asks systems to predict the publication date of the next update of a
systematic review.

## System input

The `topics/` directory contains one initial-review `.txt` topic file per
review. Each file is named with its topic identifier and contains fields such
as `Topic`, `Version`, `Title`, `Stage`, `Track`, `Year`, `Date`, and `Abstract`.

## Submission format

Submit one tab-separated file named `predictions.tsv` with the columns `topic`
and `date`. Each topic must occur once, and dates must use ISO `YYYY-MM-DD`
format.

## Hidden test truth data

The evaluator receives:

- `updated-review-topics/`, containing the gold updated review dates.

Evaluation reports topic coverage, full-date and year accuracy, signed and
absolute date error in days, and the share of topics predicted within 90 and
within 180 days of the gold date.

The truths described here are held privately in TIRA and are not part of this package.

## Reporting by track and update type

Every topic belongs to one of two tracks, and every pair has an update type:

- Track A: the initial version is a completed review and the updated version is
  an update of it (9 of 35 topics). Track B: the initial version is a protocol
  and the updated version is the first review (26 of 35 topics).
- Update type `new_content`: Cochrane marks the updated version as a new review
  or a new search for studies. Update type `edit`: it marks it as an edit of an
  existing version. Participants see `Stage` and `Track` in the topic files, but
  not the update type.

The gold date of an `edit` is the day a correction was published, not the time of a new search.

Scores are reported for all topics together and also for each track and each
update type. A group with no topic that has a new included study shows `n/a` for
the macro scores. Protocols have no included studies, so Track B topics have no
initial labels.
