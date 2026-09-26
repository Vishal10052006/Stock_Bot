"""Aggregate resolved live prediction outcomes into auditable metrics."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from ml.models.logistic import MODEL_CLASSES

from .journal import LiveValidationJournal
from .models import LivePredictionReport, OutcomeStatus


class LivePredictionEvaluator:
    """Calculate correctness, class metrics, and confusion matrix."""

    def __init__(self, journal: LiveValidationJournal) -> None:
        if not isinstance(journal, LiveValidationJournal):
            raise TypeError("journal must be a LiveValidationJournal")
        self.journal = journal

    def evaluate(self) -> LivePredictionReport:
        """Build a report from the latest outcome state for every prediction."""
        predictions = self.journal.read_events()
        prediction_rows = {
            event["prediction_id"]: event
            for event in predictions
            if event.get("event_type") == "PREDICTION"
        }
        latest_outcomes = self.journal.read_latest_outcomes()

        class_totals = {label: 0 for label in MODEL_CLASSES}
        class_correct = {label: 0 for label in MODEL_CLASSES}
        class_incorrect = {label: 0 for label in MODEL_CLASSES}

        resolved = 0
        pending = 0
        correct = 0
        incorrect = 0
        confusion = np.zeros(
            (len(MODEL_CLASSES), len(MODEL_CLASSES)),
            dtype=int,
        )
        index = {label: position for position, label in enumerate(MODEL_CLASSES)}

        for prediction_id, prediction in prediction_rows.items():
            predicted = prediction.get("predicted_class")
            if predicted not in index:
                raise ValueError(
                    f"journal prediction has invalid predicted_class: {predicted}"
                )
            outcome = latest_outcomes.get(prediction_id)
            if outcome is None or outcome.status is OutcomeStatus.PENDING:
                pending += 1
                continue

            actual = outcome.actual_class
            if actual not in index:
                raise ValueError(
                    f"journal outcome has invalid actual_class: {actual}"
                )

            resolved += 1
            class_totals[predicted] += 1
            confusion[index[actual], index[predicted]] += 1

            if predicted == actual:
                correct += 1
                class_correct[predicted] += 1
            else:
                incorrect += 1
                class_incorrect[predicted] += 1

        accuracy = correct / resolved if resolved else None

        return LivePredictionReport(
            total_predictions=len(prediction_rows),
            resolved_predictions=resolved,
            pending_predictions=pending,
            correct_predictions=correct,
            incorrect_predictions=incorrect,
            accuracy=accuracy,
            class_totals=class_totals,
            class_correct=class_correct,
            class_incorrect=class_incorrect,
            confusion_matrix=confusion,
        )

    def print_report(self) -> None:
        """Print a human-readable live prediction validation report."""
        report = self.evaluate()
        print("=" * 72)
        print("LIVE PREDICTION VALIDATION")
        print("=" * 72)
        for key, value in report.to_mapping().items():
            if key != "confusion_matrix":
                print(f"{key}: {value}")

        print()
        print("CLASS BREAKDOWN")
        print("-" * 72)
        for label in MODEL_CLASSES:
            print(
                f"{label}: "
                f"total={report.class_totals[label]} "
                f"correct={report.class_correct[label]} "
                f"incorrect={report.class_incorrect[label]}"
            )

        print()
        print("CONFUSION MATRIX")
        print("-" * 72)
        print(
            "rows=actual, columns=predicted; "
            f"order={MODEL_CLASSES}"
        )
        print(report.confusion_matrix)
