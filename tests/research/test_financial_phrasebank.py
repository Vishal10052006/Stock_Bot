from datetime import datetime, timezone

import pytest

from research.evaluation import (
    DATASET_ID,
    DATASET_VERSION,
    load_financial_phrasebank,
)


def test_financial_phrasebank_loader_parses_original_format(tmp_path):
    path = tmp_path / "Sentences_AllAgree.txt"
    path.write_text(
        "Profit increased strongly@positive\n"
        "Revenue declined sharply@negative\n"
        "The company held its position@neutral\n",
        encoding="iso-8859-1",
    )

    examples = load_financial_phrasebank(
        path,
        agreement="allagree",
        evaluation_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert len(examples) == 3
    assert [example.gold_label for example in examples] == [
        "positive",
        "negative",
        "neutral",
    ]
    assert examples[0].document.metadata["dataset_id"] == DATASET_ID
    assert examples[0].document.metadata["dataset_version"] == DATASET_VERSION
    assert examples[0].document.metadata["temporal_provenance"] == "benchmark_only"


def test_financial_phrasebank_loader_preserves_sentence_text(tmp_path):
    path = tmp_path / "Sentences_75Agree.txt"
    sentence = "The firm's outlook improved materially."
    path.write_text(f"{sentence}@positive\n", encoding="iso-8859-1")

    examples = load_financial_phrasebank(path, agreement="75agree")

    assert examples[0].document.content == sentence


def test_financial_phrasebank_rejects_unknown_agreement(tmp_path):
    path = tmp_path / "data.txt"
    path.write_text("text@positive\n", encoding="iso-8859-1")

    with pytest.raises(ValueError, match="agreement"):
        load_financial_phrasebank(path, agreement="25agree")


def test_financial_phrasebank_rejects_malformed_row(tmp_path):
    path = tmp_path / "data.txt"
    path.write_text("malformed row without label\n", encoding="iso-8859-1")

    with pytest.raises(ValueError, match="line 1"):
        load_financial_phrasebank(path)


def test_financial_phrasebank_requires_examples(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("\n", encoding="iso-8859-1")

    with pytest.raises(ValueError, match="no examples"):
        load_financial_phrasebank(path)
