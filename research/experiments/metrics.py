"""Required multiclass research metrics and effective-sample-size reporting."""
from __future__ import annotations
import math
from collections import Counter
from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True, slots=True)
class ClassificationMetrics:
    accuracy: float
    balanced_accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    per_class: dict[str, dict[str, float]]
    log_loss: float
    brier: float
    ece: float
    confusion_matrix: dict[str, dict[str, int]]
    predicted_class_distribution: dict[str, float]
    probability_distribution: dict[str, float]
    signal_frequency: float
    effective_sample_size: dict[str, float]


def evaluate(y_true, y_pred, probabilities, *, classes,
             clusters_by_date=None, clusters_by_symbol=None) -> ClassificationMetrics:
    if not (len(y_true) == len(y_pred) == len(probabilities)):
        raise ValueError("y_true, y_pred and probabilities must have equal length")
    if not y_true:
        raise ValueError("cannot evaluate an empty sample")

    matrix = {actual: {pred: 0 for pred in classes} for actual in classes}
    for actual, pred in zip(y_true, y_pred):
        matrix.setdefault(actual, {pred: 0 for pred in classes})
        matrix[actual][pred] = matrix[actual].get(pred, 0) + 1

    per_class, precisions, recalls, f1s = {}, [], [], []
    for cls in classes:
        tp = matrix.get(cls, {}).get(cls, 0)
        fp = sum(matrix[a].get(cls, 0) for a in matrix if a != cls)
        fn = sum(matrix[cls].get(p, 0) for p in classes if p != cls)
        support = tp + fn
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[cls] = {"precision": precision, "recall": recall, "f1": f1, "support": float(support)}
        precisions.append(precision); recalls.append(recall); f1s.append(f1)

    log_loss, brier = 0.0, 0.0
    for actual, probs in zip(y_true, probabilities):
        p = max(min(float(probs.get(actual, 0.0)), 1.0), 1e-15)
        log_loss -= math.log(p)
        brier += sum((float(probs.get(cls, 0.0)) - float(actual == cls)) ** 2 for cls in classes)
    n = len(y_true)
    log_loss /= n
    brier /= n

    confidence = [max(float(p.get(cls, 0.0)) for cls in classes) for p in probabilities]
    correctness = [int(a == b) for a, b in zip(y_true, y_pred)]
    ece = _ece(confidence, correctness)

    pred_counts = Counter(y_pred)
    prob_means = {cls: mean(float(p.get(cls, 0.0)) for p in probabilities) for cls in classes}
    return ClassificationMetrics(
        accuracy=sum(correctness) / n,
        balanced_accuracy=mean(recalls),
        macro_precision=mean(precisions),
        macro_recall=mean(recalls),
        macro_f1=mean(f1s),
        per_class=per_class,
        log_loss=log_loss,
        brier=brier,
        ece=ece,
        confusion_matrix=matrix,
        predicted_class_distribution={c: pred_counts.get(c, 0) / n for c in classes},
        probability_distribution=prob_means,
        signal_frequency=sum(p != "NO_EDGE" for p in y_pred) / n,
        effective_sample_size={
            "observations": float(n),
            "date_cluster_ess": _cluster_ess(y_true, clusters_by_date),
            "symbol_cluster_ess": _cluster_ess(y_true, clusters_by_symbol),
        },
    )


def majority_baseline(y_true, classes):
    counts = Counter(y_true)
    majority = max(classes, key=lambda c: counts.get(c, 0))
    prior = {c: counts.get(c, 0) / len(y_true) for c in classes}
    return [majority] * len(y_true), [prior.copy() for _ in y_true]


def _ece(confidence, correctness, bins=10):
    total, value = len(confidence), 0.0
    for index in range(bins):
        lo, hi = index / bins, (index + 1) / bins
        members = [i for i, c in enumerate(confidence) if lo <= c < hi or (index == bins - 1 and c == hi)]
        if members:
            value += len(members) / total * abs(
                mean(confidence[i] for i in members) - mean(correctness[i] for i in members)
            )
    return value


def _cluster_ess(values, clusters):
    if not clusters:
        return float(len(values))
    groups = {}
    for value, cluster in zip(values, clusters):
        groups.setdefault(cluster, []).append(value)
    if len(groups) <= 1:
        return float(len(values))
    # Conservative design-effect approximation using cluster-size inflation.
    mean_size = len(values) / len(groups)
    return len(values) / max(1.0, mean_size)
