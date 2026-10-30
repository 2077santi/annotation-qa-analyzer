# Weekly QA Report - Content Safety Annotation Program

**Scope:** 4,000 items · 20,000 labels · 25 annotators · 600 gold items · weeks 1-8

## Headline

- Inter-annotator agreement: **Fleiss' kappa 0.66** (substantial).
- Delivered label accuracy vs gold: **95.7%**.
- If the actions below are applied: **99.3%** projected (+3.7 pp).
- **9 findings, 1 critical.**

## Findings and actions

| | Type | Subject | Evidence | Action |
|---|---|---|---|---|
| 🔴 | SYSTEMATIC_BIAS | `A18` | Labels 38% of SELF_HARM items as SAFE (team: 6%, n=37) | Pull from SELF_HARM queue today and re-review their last 2 weeks of SELF_HARM labels |
| 🟠 | DRIFT | `A07` | Agreement fell from 92% (weeks 1-4) to 74% (last 2 weeks); handle time dropped 30% - likely rushing | 1:1 calibration session, then 100% QA review on next 50 tasks with a pacing check |
| 🟠 | DRIFT | `A15` | Agreement fell from 90% (weeks 1-4) to 69% (last 2 weeks); handle time dropped 26% - likely rushing | 1:1 calibration session, then 100% QA review on next 50 tasks with a pacing check |
| 🟠 | DRIFT | `A22` | Agreement fell from 87% (weeks 1-4) to 74% (last 2 weeks); handle time dropped 32% - likely rushing | 1:1 calibration session, then 100% QA review on next 50 tasks with a pacing check |
| 🟠 | GUIDELINE_AMBIGUITY | `news_reporting` | Fleiss' kappa 0.10 (slight) vs 0.77 on plain content, across all annotators | Escalate to policy team: add a decision rule + 5 worked examples for 'news_reporting' to the guideline |
| 🟠 | GUIDELINE_AMBIGUITY | `sarcasm` | Fleiss' kappa 0.12 (slight) vs 0.77 on plain content, across all annotators | Escalate to policy team: add a decision rule + 5 worked examples for 'sarcasm' to the guideline |
| 🟡 | GUIDELINE_AMBIGUITY | `reclaimed_term` | Fleiss' kappa 0.48 (moderate) vs 0.77 on plain content, across all annotators | Escalate to policy team: add a decision rule + 5 worked examples for 'reclaimed_term' to the guideline |
| 🟡 | GUIDELINE_AMBIGUITY | `satire` | Fleiss' kappa 0.51 (moderate) vs 0.77 on plain content, across all annotators | Escalate to policy team: add a decision rule + 5 worked examples for 'satire' to the guideline |
| 🟡 | SYSTEMATIC_BIAS | `A03` | Labels 23% of SAFE items as HARASSMENT (team: 4%, n=371) | Targeted calibration on the SAFE vs HARASSMENT boundary with 20 gold examples |

## Where disagreement comes from (root-cause Pareto)

| Root cause | Disagreements | Share |
|---|---:|---:|
| Individual error (noise) | 1,072 | 47% |
| Guideline ambiguity | 984 | 43% |
| Annotator drift | 161 | 7% |
| Systematic annotator bias | 78 | 3% |

## Agreement by content type

| Edge case | Items | Fleiss' kappa |
|---|---:|---:|
| news_reporting | 244 | 0.10 |
| sarcasm | 284 | 0.12 |
| reclaimed_term | 181 | 0.48 |
| satire | 182 | 0.51 |
| medical_info | 158 | 0.57 |
| none (plain content) | 2,951 | 0.77 |

## Method

- Each label is compared with the **leave-one-out majority** of the other raters (at least 3 of 4 must agree), so nobody is judged against their own vote.
- **Drift:** agreement in the last 2 weeks is at least 6 pp below the annotator's weeks 1-4 baseline *and* the drop is significant (two-proportion z-test, p < 0.01).
- **Bias:** an annotator's error rate on a specific label pair is at least 10 pp above the team's, with at least 15 reference items.
- **Guideline ambiguity:** an edge case's Fleiss' kappa is at least 0.20 below plain content - the whole team disagrees, so the rule is the problem, not the people.
- Projected accuracy re-runs majority vote without flagged annotators and assumes ambiguous edge cases go to expert adjudication.
