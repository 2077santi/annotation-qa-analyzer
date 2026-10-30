import numpy as np
import pytest

from qa.metrics import cohen_kappa, fleiss_kappa, interpret_kappa
from qa.pipeline import drop_z_score


def test_cohen_kappa_textbook_example():
    # 50 items, two raters: 20 yes/yes, 15 no/no, 5 yes/no, 10 no/yes -> kappa = 0.40
    a = ["yes"] * 25 + ["no"] * 25
    b = ["yes"] * 20 + ["no"] * 5 + ["yes"] * 10 + ["no"] * 15
    assert cohen_kappa(a, b) == pytest.approx(0.40, abs=1e-9)


def test_cohen_kappa_perfect_and_mismatched_lengths():
    assert cohen_kappa(["x", "y", "x"], ["x", "y", "x"]) == 1.0
    with pytest.raises(ValueError):
        cohen_kappa(["x"], ["x", "y"])


def test_fleiss_kappa_wikipedia_example():
    # Worked example from Fleiss (1971) as reproduced on Wikipedia: kappa = 0.210
    counts = np.array([
        [0, 0, 0, 0, 14], [0, 2, 6, 4, 2], [0, 0, 3, 5, 6], [0, 3, 9, 2, 0], [2, 2, 8, 1, 1],
        [7, 7, 0, 0, 0], [3, 2, 6, 3, 0], [2, 5, 3, 2, 2], [6, 5, 2, 1, 0], [0, 2, 2, 3, 7],
    ])
    assert fleiss_kappa(counts) == pytest.approx(0.210, abs=1e-3)


def test_fleiss_kappa_rejects_uneven_raters():
    with pytest.raises(ValueError):
        fleiss_kappa(np.array([[2, 1], [1, 1]]))


@pytest.mark.parametrize("kappa,band", [(-0.1, "poor"), (0.15, "slight"), (0.5, "moderate"), (0.7, "substantial"), (0.9, "almost perfect")])
def test_interpret_kappa(kappa, band):
    assert interpret_kappa(kappa) == band


def test_drop_z_score_separates_noise_from_real_drops():
    assert drop_z_score(0.90, 400, 0.88, 200) < 2.58   # 2 pp on ~200 labels: noise
    assert drop_z_score(0.90, 400, 0.72, 200) > 2.58   # 18 pp: real
