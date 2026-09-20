from research.evaluation.benchmark import (
    FinancialPhraseBankBenchmark,
    run_financial_phrasebank_benchmark,
)


class FakeSentimentModel:
    model_version = "fake:benchmark"

    def __init__(self):
        self.calls = 0

    def analyze(self, document):
        self.calls += 1
        text = document.content.lower()
        if "increased" in text:
            label, score = "positive", 0.8
        elif "declined" in text:
            label, score = "negative", -0.8
        else:
            label, score = "neutral", 0.7

        from research.contracts import SentimentResult

        return SentimentResult(
            label=label,
            score=score,
            confidence=0.8,
            model_version=self.model_version,
        )


def test_financial_phrasebank_benchmark_is_serializable(tmp_path):
    path = tmp_path / "Sentences_AllAgree.txt"
    path.write_text(
        "Profit increased strongly@positive\n"
        "Revenue declined sharply@negative\n"
        "The company held its position@neutral\n",
        encoding="iso-8859-1",
    )

    model = FakeSentimentModel()
    result = run_financial_phrasebank_benchmark(
        path,
        model,
        agreement="allagree",
    )

    assert isinstance(result, FinancialPhraseBankBenchmark)
    assert result.dataset_id == "financial_phrasebank"
    assert result.agreement == "allagree"
    assert result.model_version == "fake:benchmark"
    assert result.observations == 3
    assert result.accuracy == 1.0
    assert result.macro_f1 == 1.0
    assert result.to_dict()["confusion_matrix"] == (
        (1, 0, 0),
        (0, 1, 0),
        (0, 0, 1),
    )
    assert model.calls == 3
