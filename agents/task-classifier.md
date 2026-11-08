# Task classifier

Choose LIGHT or FULL by the task's impact, never its extension or line count.
Read [AGENTS.md](../AGENTS.md) and [orchestrator.md](orchestrator.md).
The orchestrator may apply these rules inline; a typo needs no separate classifier.

## LIGHT

Use only for clear, bounded, reversible work: routine docs, typos, links,
comments, cosmetic edits, or isolated developer utilities with no effect on
core runtime, contracts, security, billing, evaluation, retrieval, data,
dependencies, or infrastructure.
One implementer completes the task and a focused check, reporting its actual
result. Separate reviewer and tester assignments are unnecessary unless required.
For prose, check the diff for intended meaning and verify affected local links;
for a utility, use the smallest check that exercises the changed behavior.

## FULL

Use for functional or core changes, any sensitive area listed above,
unclear or broad work, or an explicitly required independent review/test gate.
Docs changing contracts, security, architecture, or benchmark rules are FULL.
Follow the orchestrator's implementer → reviewer → tester workflow and gates.
If impact is uncertain or expands during LIGHT work, route FULL before proceeding.

## Output and limits

Return one line or at most four bullets: route, reason, affected files, minimum check.
Classification performs no implementation, DAG edits, or process-artifact creation.
Both routes preserve task readiness, permissions, resource/connectivity gates,
host boundaries, and all explicit independent checks; routing bypasses none.
