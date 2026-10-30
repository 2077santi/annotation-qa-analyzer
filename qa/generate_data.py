"""Generate a synthetic content-safety annotation program.

The data mimics a real AI training-data project: 4,000 user posts, each labeled
by 5 of 25 annotators over 8 weeks, with an expert gold set on 15% of items.

Hidden patterns are planted on purpose so the QA pipeline has something real to
find (the pipeline never reads them; they live only in this file):
  - 3 annotators drift from week 5 (accuracy drops, handle time drops).
  - A03 over-flags SAFE posts as HARASSMENT.
  - A18 misses SELF_HARM (labels it SAFE) - a critical safety gap.
  - "news_reporting" and "sarcasm" posts are ambiguous under the guideline,
    so everyone disagrees on them, not just weak annotators.
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_ITEMS = 4_000
N_ANNOTATORS = 25
LABELS_PER_ITEM = 5
WEEKS = 8
GOLD_SHARE = 0.15

LABELS = ["SAFE", "HARASSMENT", "HATE", "SELF_HARM", "SPAM", "MISINFO"]
LABEL_MIX = [0.55, 0.12, 0.08, 0.05, 0.12, 0.08]

# Edge-case tags and how much they lower everyone's chance of being correct.
EDGE_CASES = {
    None: 0.0,
    "sarcasm": 0.28,
    "news_reporting": 0.32,
    "satire": 0.12,
    "reclaimed_term": 0.15,
    "medical_info": 0.10,
}
EDGE_MIX = [0.74, 0.07, 0.06, 0.05, 0.04, 0.04]

# When an annotator gets it wrong, which label do they pick instead?
CONFUSIONS = {
    "SAFE": ["HARASSMENT", "HATE", "SPAM", "MISINFO"],
    "HARASSMENT": ["SAFE", "HATE"],
    "HATE": ["HARASSMENT", "SAFE"],
    "SELF_HARM": ["SAFE", "HARASSMENT"],
    "SPAM": ["SAFE", "MISINFO"],
    "MISINFO": ["SAFE", "SPAM"],
}
# Edge cases push errors in a typical direction (e.g. news about violence -> HATE).
EDGE_CONFUSION = {
    "news_reporting": "HATE",
    "sarcasm": "SAFE",
    "satire": "MISINFO",
    "reclaimed_term": "HATE",
    "medical_info": "MISINFO",
}

DRIFTERS = {"A07", "A15", "A22"}
OVER_FLAGGER = "A03"
SELF_HARM_MISSER = "A18"
SITES = ["Barcelona", "Lisbon", "Manila", "Bogota"]


def _annotators(rng):
    ids = [f"A{i:02d}" for i in range(1, N_ANNOTATORS + 1)]
    return pd.DataFrame(
        {
            "annotator_id": ids,
            "site": rng.choice(SITES, size=N_ANNOTATORS),
            "tenure_months": rng.integers(2, 30, size=N_ANNOTATORS),
            "base_skill": rng.uniform(0.89, 0.97, size=N_ANNOTATORS).round(3),
        }
    )


def _items(rng):
    edge_keys = list(EDGE_CASES)
    edge_idx = rng.choice(len(edge_keys), size=N_ITEMS, p=EDGE_MIX)
    items = pd.DataFrame(
        {
            "item_id": [f"P{i:05d}" for i in range(1, N_ITEMS + 1)],
            "week": np.repeat(np.arange(1, WEEKS + 1), N_ITEMS // WEEKS),
            "content_type": rng.choice(["text", "image_caption", "comment_thread"], size=N_ITEMS, p=[0.6, 0.25, 0.15]),
            "edge_case": [edge_keys[i] for i in edge_idx],
            "true_label": rng.choice(LABELS, size=N_ITEMS, p=LABEL_MIX),
        }
    )
    # News reporting and sarcasm are mostly SAFE / HARASSMENT in reality.
    news = items["edge_case"] == "news_reporting"
    items.loc[news, "true_label"] = rng.choice(["SAFE", "MISINFO"], size=news.sum(), p=[0.85, 0.15])
    sarcasm = items["edge_case"] == "sarcasm"
    items.loc[sarcasm, "true_label"] = rng.choice(["HARASSMENT", "SAFE"], size=sarcasm.sum(), p=[0.6, 0.4])
    return items


def _p_correct(annotator, skill, week, edge_case):
    p = skill - EDGE_CASES[edge_case]
    if annotator in DRIFTERS and week >= 5:
        p -= 0.05 * (week - 4)
    return max(p, 0.3)


def _wrong_label(rng, true_label, edge_case):
    hint = EDGE_CONFUSION.get(edge_case)
    if hint and hint != true_label and rng.random() < 0.7:
        return hint
    return rng.choice(CONFUSIONS[true_label])


def _labels(rng, items, annotators):
    skill = dict(zip(annotators["annotator_id"], annotators["base_skill"]))
    ids = annotators["annotator_id"].to_numpy()
    rows = []
    start = pd.Timestamp("2026-08-03 08:00")
    for item in items.itertuples(index=False):
        edge_case = item.edge_case if isinstance(item.edge_case, str) else None  # pandas stores None as NaN
        for annotator in rng.choice(ids, size=LABELS_PER_ITEM, replace=False):
            p = _p_correct(annotator, skill[annotator], item.week, edge_case)
            label = item.true_label if rng.random() < p else _wrong_label(rng, item.true_label, edge_case)

            if annotator == OVER_FLAGGER and item.true_label == "SAFE" and rng.random() < 0.22:
                label = "HARASSMENT"
            if annotator == SELF_HARM_MISSER and item.true_label == "SELF_HARM" and rng.random() < 0.38:
                label = "SAFE"

            handle_time = rng.lognormal(mean=np.log(42), sigma=0.35)
            if edge_case:
                handle_time *= 1.4
            if annotator in DRIFTERS and item.week >= 5:
                handle_time *= 0.7  # rushing
            day_offset = pd.Timedelta(days=7 * (item.week - 1) + int(rng.integers(0, 5)), minutes=int(rng.integers(0, 540)))
            rows.append((item.item_id, annotator, label, start + day_offset, round(handle_time, 1)))

    labels = pd.DataFrame(rows, columns=["item_id", "annotator_id", "label", "labeled_at", "handle_time_sec"])
    labels.insert(0, "label_id", [f"L{i:06d}" for i in range(1, len(labels) + 1)])
    return labels


def generate(out_dir: Path, seed: int = SEED) -> None:
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)

    annotators = _annotators(rng)
    items = _items(rng)
    labels = _labels(rng, items, annotators)

    gold_ids = rng.choice(items["item_id"], size=int(N_ITEMS * GOLD_SHARE), replace=False)
    gold = items.loc[items["item_id"].isin(gold_ids), ["item_id", "true_label"]].rename(columns={"true_label": "gold_label"})

    annotators.drop(columns="base_skill").to_csv(out_dir / "annotators.csv", index=False)
    items.drop(columns="true_label").to_csv(out_dir / "items.csv", index=False)
    labels.to_csv(out_dir / "labels.csv", index=False)
    gold.to_csv(out_dir / "gold.csv", index=False)
    print(f"Wrote {len(items):,} items, {len(labels):,} labels, {len(gold):,} gold items to {out_dir}")


if __name__ == "__main__":
    generate(Path(__file__).resolve().parents[1] / "data")
