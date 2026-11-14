def points_for(correct: bool, elapsed_ms: int, window_ms: int, base: int, max_bonus: int) -> tuple[int, int]:
    """(total, speed_bonus). Wrong/blank = 0, never negative. Bonus decays linearly over the question window."""
    if not correct:
        return 0, 0
    frac = max(0.0, 1 - elapsed_ms / window_ms) if window_ms > 0 else 0.0
    bonus = round(max_bonus * frac)
    return base + bonus, bonus


def accuracy(correct: int, answered: int) -> float:
    return round(correct / answered * 100, 2) if answered else 0.0


def decide_winner(a: dict, b: dict) -> str | None:
    """Tie-break order: score, correct count, lower avg response time. Returns user_id or None for a draw.
    Each dict: user_id, score, correct, avg_rt (None => no answers => worst)."""
    inf = float("inf")
    ka = (a["score"], a["correct"], -(a["avg_rt"] if a["avg_rt"] is not None else inf))
    kb = (b["score"], b["correct"], -(b["avg_rt"] if b["avg_rt"] is not None else inf))
    return None if ka == kb else (a["user_id"] if ka > kb else b["user_id"])
