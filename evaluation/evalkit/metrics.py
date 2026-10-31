import math
import random
from typing import Callable, Sequence


def average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1  # ties share the average rank
        i = j + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Rank correlation (-1 to 1). None when it is undefined: fewer than 3 points, or one side has no variation."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    rx, ry = average_ranks(xs), average_ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if sx == 0 or sy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / (sx * sy)


def confusion(decisions: Sequence[tuple[bool, bool]]) -> dict[str, int]:
    """decisions: (gold_supported, predicted_supported). 'Supported' is the positive class."""
    c = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for gold, pred in decisions:
        c["tp" if gold and pred else "fp" if pred else "fn" if gold else "tn"] += 1
    return c


def _ratio(a: float, b: float) -> float | None:
    return a / b if b else None


def prf(c: dict[str, int]) -> dict[str, float | None]:
    p, r = _ratio(c["tp"], c["tp"] + c["fp"]), _ratio(c["tp"], c["tp"] + c["fn"])
    f1 = None if p is None or r is None or (p + r) == 0 else 2 * p * r / (p + r)
    n = sum(c.values())
    return {"precision": p, "recall": r, "f1": f1, "accuracy": _ratio(c["tp"] + c["tn"], n)}


def bootstrap_ci(items: list, stat: Callable[[list], float | None], n: int = 1000, seed: int = 7) -> tuple[float, float] | None:
    """95% percentile interval of stat(items) when items (here: labeled pairs) are resampled with replacement."""
    if len(items) < 2:
        return None
    rng = random.Random(seed)
    values = []
    for _ in range(n):
        v = stat([rng.choice(items) for _ in items])
        if v is not None:
            values.append(v)
    if len(values) < n * 0.5:
        return None
    values.sort()
    return values[int(0.025 * len(values))], values[min(len(values) - 1, int(0.975 * len(values)))]


def mean_std(values: Sequence[float]) -> tuple[float, float] | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    m = sum(vals) / len(vals)
    return m, (math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) if len(vals) > 1 else 0.0)
