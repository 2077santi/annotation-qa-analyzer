"""Write the weekly QA report a quality lead would send to the program."""

from pathlib import Path

SEVERITY_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡"}


def write_report(result: dict, path: Path) -> None:
    s = result["summary"]
    lines = [
        "# Weekly QA Report - Content Safety Annotation Program",
        "",
        f"**Scope:** {s['items']:,} items · {s['labels']:,} labels · {s['annotators']} annotators · {s['gold_items']} gold items · weeks 1-8",
        "",
        "## Headline",
        "",
        f"- Inter-annotator agreement: **Fleiss' kappa {s['fleiss_kappa']:.2f}** ({s['kappa_band']}).",
        f"- Delivered label accuracy vs gold: **{s['label_quality_now']:.1%}**.",
        f"- If the actions below are applied: **{s['label_quality_after_fixes']:.1%}** projected "
        f"(+{(s['label_quality_after_fixes'] - s['label_quality_now']) * 100:.1f} pp).",
        f"- **{s['findings']} findings, {s['critical_findings']} critical.**",
        "",
        "## Findings and actions",
        "",
        "| | Type | Subject | Evidence | Action |",
        "|---|---|---|---|---|",
    ]
    for f in result["findings"]:
        lines.append(f"| {SEVERITY_ICON[f['severity']]} | {f['kind']} | `{f['subject']}` | {f['evidence']} | {f['action']} |")

    lines += [
        "",
        "## Where disagreement comes from (root-cause Pareto)",
        "",
        "| Root cause | Disagreements | Share |",
        "|---|---:|---:|",
    ]
    for row in result["pareto"]:
        lines.append(f"| {row['root_cause']} | {row['disagreements']:,} | {row['share']:.0%} |")

    lines += [
        "",
        "## Agreement by content type",
        "",
        "| Edge case | Items | Fleiss' kappa |",
        "|---|---:|---:|",
    ]
    for row in sorted(result["edge_kappa"], key=lambda r: r["kappa"]):
        lines.append(f"| {row['edge_case']} | {row['items']:,} | {row['kappa']:.2f} |")

    lines += [
        "",
        "## Method",
        "",
        "- Each label is compared with the **leave-one-out majority** of the other raters (at least 3 of 4 must agree), so nobody is judged against their own vote.",
        "- **Drift:** agreement in the last 2 weeks is at least 6 pp below the annotator's weeks 1-4 baseline *and* the drop is significant (two-proportion z-test, p < 0.01).",
        "- **Bias:** an annotator's error rate on a specific label pair is at least 10 pp above the team's, with at least 15 reference items.",
        "- **Guideline ambiguity:** an edge case's Fleiss' kappa is at least 0.20 below plain content - the whole team disagrees, so the rule is the problem, not the people.",
        "- Projected accuracy re-runs majority vote without flagged annotators and assumes ambiguous edge cases go to expert adjudication.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
