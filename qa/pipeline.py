"""Run the weekly QA analysis: agreement, drift, bias, ambiguity, root causes."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from qa.metrics import fleiss_kappa, interpret_kappa

ROOT = Path(__file__).resolve().parents[1]

# Thresholds a QA lead would agree with up front (see SPEC.md).
DRIFT_DROP = 0.06          # recent agreement this far below own baseline
DRIFT_Z = 2.58             # ...and the drop is significant (two-proportion z-test, p < 0.01)
BIAS_EXCESS = 0.10         # error rate on a label pair this far above the team rate
BIAS_MIN_SUPPORT = 15      # ignore label pairs with fewer reference items
AMBIGUITY_GAP = 0.20       # edge-case kappa this far below the plain-content kappa
CRITICAL_MISSES = {("SELF_HARM", "SAFE"), ("HATE", "SAFE")}


@dataclass
class Finding:
    kind: str           # DRIFT | SYSTEMATIC_BIAS | GUIDELINE_AMBIGUITY
    subject: str        # annotator id or edge-case tag
    severity: str       # critical | high | medium
    evidence: str
    action: str
    label_pair: tuple[str, str] | None = None  # (reference, given) for bias findings


def load(con: duckdb.DuckDBPyConnection, data_dir: Path) -> None:
    for table in ["items", "labels", "gold", "annotators"]:
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_csv_auto('{data_dir / table}.csv')")
    con.execute((ROOT / "sql" / "views.sql").read_text())


def vote_matrix(con, where: str = "TRUE") -> np.ndarray:
    votes = con.execute(
        f"SELECT v.item_id, v.label, v.votes FROM item_votes v JOIN items i USING (item_id) WHERE {where}"
    ).df()
    return votes.pivot_table(index="item_id", columns="label", values="votes", fill_value=0).to_numpy()


def _pooled_rate(rows: pd.DataFrame) -> tuple[float, int]:
    n = rows["labels_scored"].sum()
    return float((rows["agreement_rate"] * rows["labels_scored"]).sum() / n), int(n)


def drop_z_score(p1: float, n1: int, p2: float, n2: int) -> float:
    """Two-proportion z-test: how many standard errors p2 sits below p1."""
    pooled = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = np.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    return float((p1 - p2) / se) if se else 0.0


def detect_drift(weekly: pd.DataFrame) -> list[Finding]:
    findings = []
    last_week = weekly["week"].max()
    for annotator, rows in weekly.groupby("annotator_id"):
        baseline, n_base = _pooled_rate(rows[rows["week"] <= 4])
        recent_rows = rows[rows["week"] > last_week - 2]
        recent, n_recent = _pooled_rate(recent_rows)
        if baseline - recent < DRIFT_DROP or drop_z_score(baseline, n_base, recent, n_recent) < DRIFT_Z:
            continue
        aht_before = rows.loc[rows["week"] <= 4, "avg_handle_time_sec"].mean()
        aht_after = recent_rows["avg_handle_time_sec"].mean()
        rushing = aht_after < aht_before * 0.85
        findings.append(
            Finding(
                kind="DRIFT",
                subject=annotator,
                severity="high",
                evidence=(
                    f"Agreement fell from {baseline:.0%} (weeks 1-4) to {recent:.0%} (last 2 weeks)"
                    + (f"; handle time dropped {1 - aht_after / aht_before:.0%} - likely rushing" if rushing else "")
                ),
                action="1:1 calibration session, then 100% QA review on next 50 tasks"
                + (" with a pacing check" if rushing else ""),
            )
        )
    return findings


def detect_bias(confusion: pd.DataFrame) -> list[Finding]:
    support = confusion.groupby(["annotator_id", "reference_label"])["n"].transform("sum")
    confusion = confusion.assign(rate=confusion["n"] / support, support=support)
    team = confusion.groupby(["reference_label", "label"])["n"].sum()
    team_rate = team / team.groupby(level=0).transform("sum")
    confusion["team_rate"] = [team_rate.get((r, l), 0.0) for r, l in zip(confusion["reference_label"], confusion["label"])]

    errors = confusion[(confusion["reference_label"] != confusion["label"]) & (confusion["support"] >= BIAS_MIN_SUPPORT)]
    flagged = errors[errors["rate"] - errors["team_rate"] >= BIAS_EXCESS]

    findings = []
    for row in flagged.itertuples(index=False):
        critical = (row.reference_label, row.label) in CRITICAL_MISSES
        findings.append(
            Finding(
                kind="SYSTEMATIC_BIAS",
                subject=row.annotator_id,
                severity="critical" if critical else "medium",
                evidence=(
                    f"Labels {row.rate:.0%} of {row.reference_label} items as {row.label} "
                    f"(team: {row.team_rate:.0%}, n={row.support})"
                ),
                action=(
                    f"Pull from {row.reference_label} queue today and re-review their last 2 weeks of {row.reference_label} labels"
                    if critical
                    else f"Targeted calibration on the {row.reference_label} vs {row.label} boundary with 20 gold examples"
                ),
                label_pair=(row.reference_label, row.label),
            )
        )
    return findings


def detect_ambiguity(con) -> tuple[list[Finding], pd.DataFrame]:
    plain = fleiss_kappa(vote_matrix(con, "i.edge_case IS NULL"))
    rows = [{"edge_case": "none (plain content)", "kappa": plain, "items": int(con.execute("SELECT COUNT(*) FROM items WHERE edge_case IS NULL").fetchone()[0])}]
    findings = []
    for (edge_case,) in con.execute("SELECT DISTINCT edge_case FROM items WHERE edge_case IS NOT NULL ORDER BY 1").fetchall():
        kappa = fleiss_kappa(vote_matrix(con, f"i.edge_case = '{edge_case}'"))
        items = int(con.execute(f"SELECT COUNT(*) FROM items WHERE edge_case = '{edge_case}'").fetchone()[0])
        rows.append({"edge_case": edge_case, "kappa": kappa, "items": items})
        if plain - kappa >= AMBIGUITY_GAP:
            findings.append(
                Finding(
                    kind="GUIDELINE_AMBIGUITY",
                    subject=edge_case,
                    severity="high" if kappa < 0.4 else "medium",
                    evidence=f"Fleiss' kappa {kappa:.2f} ({interpret_kappa(kappa)}) vs {plain:.2f} on plain content, across all annotators",
                    action=f"Escalate to policy team: add a decision rule + 5 worked examples for '{edge_case}' to the guideline",
                )
            )
    return findings, pd.DataFrame(rows)


def attribute_root_causes(con, findings: list[Finding]) -> pd.DataFrame:
    """Assign every disagreement with the reference to one root cause."""
    disagreements = con.execute("SELECT * FROM label_reference WHERE NOT agrees").df()
    ambiguous = {f.subject for f in findings if f.kind == "GUIDELINE_AMBIGUITY"}
    drifting = {f.subject for f in findings if f.kind == "DRIFT"}
    biased = {(f.subject, *f.label_pair) for f in findings if f.kind == "SYSTEMATIC_BIAS"}
    last_week = int(con.execute("SELECT MAX(week) FROM items").fetchone()[0])

    def cause(row) -> str:
        if row.edge_case in ambiguous:
            return "Guideline ambiguity"
        if (row.annotator_id, row.reference_label, row.label) in biased:
            return "Systematic annotator bias"
        if row.annotator_id in drifting and row.week >= last_week - 3:
            return "Annotator drift"
        return "Individual error (noise)"

    disagreements["root_cause"] = [cause(r) for r in disagreements.itertuples(index=False)]
    return disagreements


def label_quality(con, exclude: tuple[str, ...] = (), adjudicate: tuple[str, ...] = ()) -> float:
    """Gold accuracy of the delivered (majority-vote) label.

    `exclude` drops annotators' votes; `adjudicate` sends those edge cases to an
    expert, modeled as resolving them to the gold label.
    """
    excluded = ", ".join(f"'{a}'" for a in exclude) or "''"
    votes = con.execute(
        f"""
        SELECT l.item_id, l.label, COUNT(*) AS votes, i.edge_case, g.gold_label
        FROM labels l JOIN gold g USING (item_id) JOIN items i USING (item_id)
        WHERE l.annotator_id NOT IN ({excluded})
        GROUP BY ALL
        """
    ).df()
    top = votes.sort_values(["item_id", "votes", "label"], ascending=[True, False, True]).drop_duplicates("item_id")
    correct = (top["label"] == top["gold_label"]) | top["edge_case"].isin(adjudicate)
    return float(correct.mean())


def run(data_dir: Path = ROOT / "data", out_dir: Path = ROOT) -> dict:
    con = duckdb.connect()
    load(con, data_dir)

    weekly = con.execute("SELECT * FROM annotator_weekly ORDER BY annotator_id, week").df()
    gold = con.execute("SELECT * FROM annotator_gold ORDER BY annotator_id").df()
    confusion = con.execute("SELECT * FROM annotator_confusion").df()

    ambiguity_findings, edge_kappa = detect_ambiguity(con)
    findings = detect_bias(confusion) + detect_drift(weekly) + ambiguity_findings
    order = {"critical": 0, "high": 1, "medium": 2}
    findings.sort(key=lambda f: (order[f.severity], f.kind, f.subject))

    causes = attribute_root_causes(con, findings)
    pareto = causes["root_cause"].value_counts().rename_axis("root_cause").reset_index(name="disagreements")
    pareto["share"] = pareto["disagreements"] / pareto["disagreements"].sum()

    flagged_annotators = tuple(sorted({f.subject for f in findings if f.kind in ("DRIFT", "SYSTEMATIC_BIAS")}))
    ambiguous_cases = tuple(f.subject for f in findings if f.kind == "GUIDELINE_AMBIGUITY")
    quality_now = label_quality(con)
    quality_after = label_quality(con, exclude=flagged_annotators, adjudicate=ambiguous_cases)

    overall_kappa = fleiss_kappa(vote_matrix(con))
    team_weekly = con.execute(
        "SELECT week, AVG(agrees::INT) AS agreement_rate, COUNT(*) AS labels FROM label_reference GROUP BY week ORDER BY week"
    ).df()
    scorecard = (
        weekly.groupby("annotator_id")
        .agg(labels_scored=("labels_scored", "sum"), agreement_rate=("agreement_rate", "mean"), avg_handle_time_sec=("avg_handle_time_sec", "mean"))
        .reset_index()
        .merge(gold, on="annotator_id")
        .merge(con.execute("SELECT * FROM annotators").df(), on="annotator_id")
    )
    scorecard["flags"] = [", ".join(sorted({f.kind for f in findings if f.subject == a})) for a in scorecard["annotator_id"]]

    summary = {
        "items": int(con.execute("SELECT COUNT(*) FROM items").fetchone()[0]),
        "labels": int(con.execute("SELECT COUNT(*) FROM labels").fetchone()[0]),
        "annotators": int(con.execute("SELECT COUNT(*) FROM annotators").fetchone()[0]),
        "gold_items": int(con.execute("SELECT COUNT(*) FROM gold").fetchone()[0]),
        "fleiss_kappa": overall_kappa,
        "kappa_band": interpret_kappa(overall_kappa),
        "label_quality_now": quality_now,
        "label_quality_after_fixes": quality_after,
        "critical_findings": sum(f.severity == "critical" for f in findings),
        "findings": len(findings),
    }
    result = {
        "summary": summary,
        "findings": [asdict(f) for f in findings],
        "pareto": pareto.to_dict("records"),
        "edge_kappa": edge_kappa.to_dict("records"),
        "team_weekly": team_weekly.to_dict("records"),
        "annotator_weekly": weekly.to_dict("records"),
        "scorecard": scorecard.sort_values("agreement_rate").to_dict("records"),
    }

    (out_dir / "reports").mkdir(exist_ok=True)
    (out_dir / "reports" / "qa_results.json").write_text(json.dumps(result, indent=2, default=float))
    return result


if __name__ == "__main__":
    from qa.report import write_report
    from qa.dashboard import build_dashboard

    result = run()
    write_report(result, ROOT / "reports" / "weekly_qa_report.md")
    build_dashboard(result, ROOT / "docs" / "index.html")
    s = result["summary"]
    print(f"{s['findings']} findings ({s['critical_findings']} critical). Label quality {s['label_quality_now']:.1%} -> {s['label_quality_after_fixes']:.1%}")
