"""Paired, fully judged ranking metrics. Unjudged candidates are an error."""
import math
import random
import statistics


def ranking_metrics(order, judgments, k=10):
    if len(order) != len(set(order)) or set(order) - set(judgments):
        raise ValueError("Duplicate or unjudged candidate; do not infer irrelevance")
    if any(type(v) is not int or not 0 <= v <= 3 for v in judgments.values()):
        raise ValueError("Graded relevance must be reviewed integers 0..3")
    dcg = lambda grades: sum((2**g-1)/math.log2(i+2) for i, g in enumerate(grades))
    ideal = dcg(sorted(judgments.values(), reverse=True)[:k])
    relevant = {d for d, grade in judgments.items() if grade > 0}
    return {"ndcg10": dcg([judgments[d] for d in order[:k]])/ideal if ideal else 1.0,
            "mrr": next((1/(i+1) for i, d in enumerate(order) if d in relevant), 0.0),
            "recall": len(relevant & set(order[:k]))/len(relevant) if relevant else 1.0,
            "precision": len(relevant & set(order[:k]))/k}


def paired_report(cases, *, seed=20261027, samples=2000):
    if not cases:
        raise ValueError("No judged queries")
    rows = []
    for c in cases:
        b = ranking_metrics(c["baseline"], c["judgments"])
        n = ranking_metrics(c["candidate"], c["judgments"])
        rows.append({"category": c["category"], "baseline": b, "candidate": n,
                     "delta": n["ndcg10"]-b["ndcg10"]})
    delta = [r["delta"] for r in rows]
    rng = random.Random(seed)
    boots = sorted(statistics.mean(rng.choices(delta, k=len(delta))) for _ in range(samples))
    return {"version": 1, "queries": len(rows), "mean_ndcg10_delta": statistics.mean(delta),
            "paired_lower95": boots[int(samples*.025)], "paired_upper95": boots[int(samples*.975)],
            "categories": {cat: statistics.mean(r["delta"] for r in rows if r["category"] == cat)
                           for cat in sorted({r["category"] for r in rows})}, "rows": rows}


def calibration(probabilities, labels, bins=10):
    if len(probabilities) != len(labels) or not labels:
        raise ValueError("Calibration needs paired reviewed labels")
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        raise ValueError("Invalid probability")
    if any(type(y) is not int or y not in (0, 1) for y in labels):
        raise ValueError("Invalid reviewed label")
    buckets = []
    for i in range(bins):
        pairs = [(p, y) for p, y in zip(probabilities, labels) if min(int(p*bins), bins-1) == i]
        if pairs:
            buckets.append({"bin": i, "count": len(pairs), "mean_probability": statistics.mean(p for p,y in pairs),
                            "observed_positive": statistics.mean(y for p,y in pairs)})
    return {"brier": statistics.mean((p-y)**2 for p,y in zip(probabilities,labels)),
            "ece": sum(b["count"]*abs(b["mean_probability"]-b["observed_positive"]) for b in buckets)/len(labels),
            "buckets": buckets}
