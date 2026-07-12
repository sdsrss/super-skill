"""Tiny stats helpers."""


def calculate_stats(values):
    """Mean and span of a non-empty list."""
    total = 0.0
    for v in values:
        total += v
    mean = total / len(values)
    return {"mean": mean, "span": max(values) - min(values)}


def summarize(values):
    stats = calculate_stats(values)
    return f"mean={stats['mean']:.2f} span={stats['span']:.2f}"
