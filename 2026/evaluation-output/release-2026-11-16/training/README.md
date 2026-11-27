# Corrected-release local training evaluation

Generated on 2026-11-16 using the updated public evaluators and the corrected
20-topic public training packages. These are local results, not TIRA results.
No hidden test topics or test scores occur in these reports.

| Task | Baseline | Training result |
| --- | --- | --- |
| 1 | Initial date + 24 months | year accuracy 0.450; full-date accuracy 0.000; MAE 279.850 days; within 90/180 days 0.150/0.300 |
| 2 | Execute the initial query | macro precision 0.020; macro recall 0.570; macro F1 0.035; macro F3 0.096; micro recall 0.585 |
| 3 | Predict every candidate as included | macro precision 0.032; macro recall 1.000; macro F1 0.060; macro F3 0.206 |

Task 3 macro scores cover 16 topics with new positives. Four zero-positive
topics are excluded from macro scores and remain in micro scores. All
predictions are valid. Task 1 and Task 2 topic coverage is 1.000.

The `task-N/` directories contain text and JSON reports plus TIRA-compatible
`evaluation.prototext`. Reports include track and update-type breakdowns.
Predictions are stored separately under
[baseline-output](../../../baseline-output/README.md).

Task 2 uses the saved Orbit run after exact query matching and split filtering,
not a fresh API retrieval. Its provenance is recorded with the submissions.
The three baseline methods are unchanged.

See the [repository README](../../../../README.md) for reproduction commands.
These 20-topic scores must not be compared directly with full-set or test scores.
