"""Production Research Bot tests."""
from datetime import datetime, timedelta, timezone

from research.contracts import ResearchDocument
from research.datasets.builder import ResearchDatasetBuilder
from research.entities.master import EntityMaster
from research.experiments.metrics import evaluate, majority_baseline
from research.features.builder import ResearchFeatureBuilder
from research.retrieval.hybrid import HybridResearchRetriever
from research.validation.leakage import ResearchLeakageAuditor
from research.validation.walk_forward import build_walk_forward_folds

UTC = timezone.utc


def doc(symbol="RELIANCE", minutes=0, content="earnings growth strong"):
    published = datetime(2026, 9, 20, 9, 0, tzinfo=UTC)
    available = published + timedelta(minutes=minutes)
    return ResearchDocument(
        document_id=f"doc-{minutes}",
        source_id="test",
        external_id=f"x-{minutes}",
        title="Research",
        content=content,
        published_at=published,
        observed_at=available,
        processed_at=available,
        available_at=available,
        symbols=(symbol,),
    )


def test_dataset_builder_is_point_in_time():
    decision = datetime(2026, 9, 20, 9, 5, tzinfo=UTC)
    row = ResearchDatasetBuilder().build_row(
        symbol="RELIANCE", decision_time=decision,
        documents=(doc(minutes=0), doc(minutes=10)), dataset_version="test-v1",
    )
    assert row.features["research_doc_count"] == 1.0
    assert row.source_document_ids == ("doc-0",)


def test_feature_builder_excludes_future_document():
    decision = datetime(2026, 9, 20, 9, 5, tzinfo=UTC)
    features = ResearchFeatureBuilder().build((doc(minutes=10),), symbol="RELIANCE", decision_time=decision)
    assert features["research_doc_count"] == 0.0


def test_leakage_auditor_detects_future_row():
    from research.datasets.schema import ResearchDatasetRow
    row = ResearchDatasetRow(
        dataset_version="x", symbol="RELIANCE",
        decision_time=datetime(2026, 9, 20, 9, 5, tzinfo=UTC),
        feature_available_at=datetime(2026, 9, 20, 9, 6, tzinfo=UTC),
        features={"research_doc_count": 1.0},
    )
    findings = ResearchLeakageAuditor().audit((row,))
    assert any(f.code == "ROW_VALIDATION" for f in findings)


def test_metrics_include_required_outputs():
    y_true = ["LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE", "NO_EDGE"]
    y_pred = ["LONG_SUCCESS", "NO_EDGE", "NO_EDGE", "NO_EDGE"]
    probs = [
        {"LONG_SUCCESS": .8, "SHORT_SUCCESS": .1, "NO_EDGE": .1},
        {"LONG_SUCCESS": .1, "SHORT_SUCCESS": .2, "NO_EDGE": .7},
        {"LONG_SUCCESS": .1, "SHORT_SUCCESS": .1, "NO_EDGE": .8},
        {"LONG_SUCCESS": .1, "SHORT_SUCCESS": .1, "NO_EDGE": .8},
    ]
    metrics = evaluate(y_true, y_pred, probs, classes=("LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"))
    assert 0 <= metrics.accuracy <= 1
    assert 0 <= metrics.balanced_accuracy <= 1
    assert metrics.log_loss >= 0
    assert metrics.brier >= 0
    assert 0 <= metrics.ece <= 1
    assert set(metrics.per_class) == {"LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"}


def test_majority_baseline():
    pred, probs = majority_baseline(
        ["NO_EDGE", "NO_EDGE", "LONG_SUCCESS"],
        ("LONG_SUCCESS", "SHORT_SUCCESS", "NO_EDGE"),
    )
    assert pred == ["NO_EDGE", "NO_EDGE", "NO_EDGE"]
    assert probs[0]["NO_EDGE"] == 2 / 3


def test_entity_master():
    path = __import__("pathlib").Path("/tmp/stockbot-entities.csv")
    path.write_text("symbol,company_name,isin
REL,Reliance Industries Limited,INE002A01018
", encoding="utf-8")
    master = EntityMaster.from_csv(path)
    assert master.resolve("Reliance Industries Limited") == "REL"


def test_causal_retrieval():
    decision = datetime(2026, 9, 20, 9, 5, tzinfo=UTC)
    hits = HybridResearchRetriever().search(
        (doc(minutes=0), doc(minutes=10)), "earnings growth",
        as_of=decision, top_k=5,
    )
    assert [hit.document_id for hit in hits] == ["doc-0"]


def test_walk_forward_has_purge():
    times = [datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i) for i in range(20)]
    folds = build_walk_forward_folds(
        times, train_size=8, validation_size=3, test_size=3,
        purge=timedelta(days=2),
    )
    assert folds
    assert all(times[i] < times[fold.validation_indices[0]] for i in folds[0].train_indices)


def test_research_feature_schema_has_no_target():
    decision = datetime(2026, 9, 20, 9, 5, tzinfo=UTC)
    row = ResearchDatasetBuilder().build_row(
        symbol="RELIANCE", decision_time=decision,
        documents=(doc(minutes=0),), dataset_version="test-v1",
    )
    assert "future_return" not in row.features
