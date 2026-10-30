"""Inter-annotator agreement metrics, implemented from the definitions."""

from collections.abc import Sequence

import numpy as np


def cohen_kappa(a: Sequence, b: Sequence) -> float:
    """Agreement between two raters on the same items, corrected for chance.

    kappa = (p_observed - p_expected) / (1 - p_expected)
    """
    a, b = np.asarray(a), np.asarray(b)
    if len(a) != len(b) or len(a) == 0:
        raise ValueError("both raters need the same, non-empty list of items")
    categories = np.union1d(a, b)
    p_observed = np.mean(a == b)
    p_expected = sum(np.mean(a == c) * np.mean(b == c) for c in categories)
    if p_expected == 1:
        return 1.0
    return float((p_observed - p_expected) / (1 - p_expected))


def fleiss_kappa(counts: np.ndarray) -> float:
    """Agreement among a fixed number of raters per item.

    `counts` is an (items x categories) matrix: counts[i, j] is how many raters
    put item i in category j. Every row must sum to the same number of raters.
    """
    counts = np.asarray(counts, dtype=float)
    n_raters = counts.sum(axis=1)
    if not np.all(n_raters == n_raters[0]):
        raise ValueError("every item needs the same number of ratings")
    n = n_raters[0]
    if n < 2:
        raise ValueError("need at least two raters per item")

    p_items = ((counts * (counts - 1)).sum(axis=1)) / (n * (n - 1))
    p_bar = p_items.mean()
    p_categories = counts.sum(axis=0) / counts.sum()
    p_expected = (p_categories**2).sum()
    if p_expected == 1:
        return 1.0
    return float((p_bar - p_expected) / (1 - p_expected))


def interpret_kappa(kappa: float) -> str:
    """Landis & Koch (1977) bands, the scale most QA teams quote."""
    if kappa < 0:
        return "poor"
    for limit, band in [(0.2, "slight"), (0.4, "fair"), (0.6, "moderate"), (0.8, "substantial")]:
        if kappa <= limit:
            return band
    return "almost perfect"
