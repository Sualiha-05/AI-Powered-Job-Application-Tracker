import pytest

from evalkit.metrics import average_ranks, bootstrap_ci, confusion, mean_std, prf, spearman


def test_average_ranks_share_ties():
    assert average_ranks([10, 20, 20, 30]) == [1, 2.5, 2.5, 4]


def test_spearman_known_values():
    assert spearman([1, 2, 3, 4, 5], [2, 1, 4, 3, 5]) == pytest.approx(0.8)  # 1 - 6*4 / (5*24)
    assert spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)
    assert spearman([1, 2, 3], [30, 20, 10]) == pytest.approx(-1.0)


def test_spearman_is_undefined_not_zero_when_it_cannot_be_computed():
    assert spearman([1, 2], [1, 2]) is None            # too few points
    assert spearman([1, 1, 1], [1, 2, 3]) is None      # one side never changes
    assert spearman([1, 2, 3], [1, 2]) is None         # mismatched lengths


def test_confusion_and_prf():
    c = confusion([(True, True), (True, False), (False, True), (False, False)])
    assert c == {"tp": 1, "fn": 1, "fp": 1, "tn": 1}
    assert prf(c) == {"precision": 0.5, "recall": 0.5, "f1": 0.5, "accuracy": 0.5}


def test_prf_handles_empty_classes_without_dividing_by_zero():
    m = prf(confusion([(True, False), (True, False)]))   # matcher never says "supported"
    assert m["recall"] == 0 and m["precision"] is None and m["f1"] is None
    assert prf(confusion([]))["accuracy"] is None


def test_bootstrap_is_reproducible_and_brackets_the_estimate():
    hit, miss = [(True, True)] * 4, [(True, False)] * 4          # half the pairs are found, half are missed
    items = [hit] * 10 + [miss] * 10
    stat = lambda s: prf(confusion([d for p in s for d in p]))["recall"]
    a, b = bootstrap_ci(items, stat), bootstrap_ci(items, stat)
    assert a == b                                                  # fixed seed: same answer every time
    assert a[0] < 0.5 < a[1] and a[1] - a[0] < 0.6                 # brackets the true 0.5, and is not absurdly wide
    assert bootstrap_ci([hit], stat) is None                       # one pair cannot be resampled


def test_mean_std():
    assert mean_std([1.0, 3.0]) == (2.0, pytest.approx(1.4142, abs=1e-3))
    assert mean_std([2.0]) == (2.0, 0.0)
    assert mean_std([None]) is None
