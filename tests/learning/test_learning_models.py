import pytest

from learning.models import (
    LearningConfig,
    LearningExperience,
    LearningPattern,
)


def test_learning_config_defaults() -> None:
    config = LearningConfig()

    assert config.minimum_evidence == 3
    assert config.minimum_occurrence_rate == 0.50


def test_learning_experience_validates_counts() -> None:
    experience = LearningExperience(
        pattern=LearningPattern.LOSS,
        symbol="ITC",
        evidence_count=3,
        population_count=5,
        occurrence_rate=0.6,
        confidence=0.4,
        source_trade_ids=("a", "b", "c"),
    )

    assert experience.evidence_count == 3
    assert experience.population_count == 5


def test_learning_experience_rejects_invalid_counts() -> None:
    with pytest.raises(ValueError):
        LearningExperience(
            pattern=LearningPattern.LOSS,
            symbol="ITC",
            evidence_count=4,
            population_count=3,
            occurrence_rate=1.0,
            confidence=0.5,
            source_trade_ids=("a", "b", "c", "d"),
        )


def test_learning_experience_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError):
        LearningExperience(
            pattern=LearningPattern.LOSS,
            symbol="ITC",
            evidence_count=3,
            population_count=5,
            occurrence_rate=0.6,
            confidence=1.5,
            source_trade_ids=("a", "b", "c"),
        )
