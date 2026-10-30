# Spec - Annotation QA Analyzer

## Context

A content-safety labeling program delivers labels from 25 annotators, with 5 labels per item and a 15% expert gold set. The QA lead needs a weekly view that says *what* is wrong with quality, *who or what* is causing it, and *what to do*, not only a single agreement number.

## Users

- **QA lead**: decides calibration sessions and review sampling.
- **Program / project manager**: reports quality to the client and plans capacity.
- **Policy team**: owns the labeling guideline.

## Out of scope

Real-time monitoring, annotator-facing feedback UI, and adjudication tooling.

## Requirements (EARS format)

### Agreement

- **R1.** The system shall compute Fleiss' kappa for the whole program and for each edge-case tag.
- **R2.** The system shall compare each label with the majority of the *other* raters on the same item, and shall only use items where at least 3 of the 4 other raters agree.

### Drift

- **R3.** When an annotator's agreement in the last 2 weeks is at least 6 pp below their weeks 1-4 baseline **and** the drop is significant at p < 0.01 (two-proportion z-test), the system shall raise a `DRIFT` finding.
- **R4.** When a drifting annotator's average handle time also dropped by more than 15%, the system shall say they are likely rushing and add a pacing check to the action.

### Bias

- **R5.** When an annotator's rate of labeling reference class X as class Y is at least 10 pp above the team's rate for the same pair, with at least 15 reference items of class X, the system shall raise a `SYSTEMATIC_BIAS` finding.
- **R6.** If the pair is (`SELF_HARM` → `SAFE`) or (`HATE` → `SAFE`), then the system shall mark the finding `critical` and recommend removing the annotator from that queue the same day.

### Guideline ambiguity

- **R7.** When an edge case's kappa is at least 0.20 below the kappa on plain content, the system shall raise a `GUIDELINE_AMBIGUITY` finding addressed to the policy team, with severity `high` below kappa 0.40 and `medium` otherwise.

### Reporting

- **R8.** The system shall assign every disagreement to exactly one root cause (ambiguity, bias, drift, noise), in that order of precedence.
- **R9.** The system shall project delivered label accuracy against gold after excluding flagged annotators and adjudicating ambiguous edge cases.
- **R10.** The system shall produce a Markdown report and a static HTML dashboard from the same results file.

## Acceptance tests

| Req | Test |
|---|---|
| R1 | `test_fleiss_kappa_wikipedia_example` matches the published value (0.210) |
| R3 | `test_finds_every_drifting_annotator_and_no_one_else`, `test_drop_z_score_separates_noise_from_real_drops` |
| R5, R6 | `test_flags_the_missed_self_harm_as_critical`, `test_finds_the_over_flagger` |
| R7 | `test_blames_the_guideline_for_news_and_sarcasm` |
| R9 | `test_actions_improve_projected_quality` |

## Open questions for the program

- Is 6 pp the right drift trigger for this client, or is it contractually defined?
- Should bias findings on non-critical pairs go to the annotator directly or through their team lead?
