# Baseline submissions for the corrected release

Prepared on 2026-11-16 using the public baseline code and corrected inputs.
Training directories cover 20 topics; test directories cover 15 topics.
These are predictions, not ground truth or live TIRA evaluation results.

- Task 1: the initial date plus 24 months.
- Task 2: the initial executable query and its retrieved PMIDs.
- Task 3: every input candidate predicted as included.

Tasks 1 and 3 were rerun separately for both splits. Task 2 queries were
regenerated with the public baseline and matched exactly against the queries
of the existing cached Orbit run. That run was partitioned by split without
using relevance labels or making a fresh Orbit request. The SHA256 of its
uncompressed content is
`93d9f998c160bd0edbb1d410746902eedfd3992819ce312eafe02a3e780e801d`.
Future fresh API runs may differ if the retrieval collection changes.

Each Task 2 directory includes `queries.tsv`, `run.txt.gz` and
`upload-to-tira.zip`. The ZIP contains only those two submission files at its
root. No test truths or test evaluation scores are included.

See the [repository README](../../README.md) for regeneration commands and the
[training evaluation](../evaluation-output/release-2026-11-16/training/README.md)
for local scores on public training truths.
