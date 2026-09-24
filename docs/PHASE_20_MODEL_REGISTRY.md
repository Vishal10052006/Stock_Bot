# STOCK BOT — Phase 20 Model Registry

**Status:** IN PROGRESS — registry implementation and CI validation  
**Module:** `ml/model_registry.py`

## Objective

Phase 20 establishes the authoritative metadata boundary for versioned model
artifacts.

The registry records **what model artifact exists, which data/code/features
produced it, which research lineage it belongs to, and which evaluation
evidence is associated with it**.

It does not train models, alter strategy/risk configuration, submit orders, or
enable live trading.

## Registry lifecycle

```
Research Model
    ↓
REGISTER
    ↓
RESEARCH_ONLY / CANDIDATE
    ↓
Controlled evaluation evidence
    ↓
Explicit governance approval
    ↓
APPROVED
    ↓
RETIRE
```

Approval is not inferred from a metric, a backtest result, or a candidate
status. The registry requires explicit `ModelApproval` evidence.

## Version identity

Every `ModelRegistryRecord` contains:

- model version;
- model family;
- feature version;
- dataset version;
- code version;
- training/validation/test periods;
- hyperparameters;
- measured metrics;
- artifact URI;
- artifact SHA-256 fingerprint;
- strategy version when applicable;
- experiment lineage ID;
- evaluation fingerprint;
- approval reference when approved.

The complete registry record has a deterministic SHA-256 fingerprint.

## Artifact and lineage boundary

A model artifact is identified independently from its metadata record.

For an approved model, the registry requires:

1. a valid artifact SHA-256 fingerprint;
2. a valid experiment lineage identity;
3. a valid evaluation fingerprint;
4. explicit approval evidence.

This prevents an approved registry entry from being created as metadata only.

## Immutability

Registry records are frozen.

Hyperparameter and metric mappings are recursively frozen so callers cannot
mutate the registered metadata after construction.

Model versions are append-only:

- registering the same version with identical metadata is idempotent;
- registering the same version with different metadata fails;
- approval creates a new immutable state;
- retirement creates a new immutable state;
- prior states remain available through `ModelRegistry.history(...)`.

Historical identities are therefore preserved instead of silently overwritten.

## Safety boundary

The registry does **not**:

- retrain models;
- modify model weights;
- modify StrategyConfig;
- modify RiskConfig;
- authorize trades;
- create broker orders;
- enable live execution;
- infer profitability;
- automatically promote a model.

The registry is a provenance/governance store, not an execution authority.

## Existing Phase 9 compatibility

The existing Phase-9 `ModelRegistryRecord` contract remains the public record
type, but Phase 20 extends it with artifact, strategy, lineage, evaluation, and
approval provenance.

This avoids creating a parallel model-registry implementation.

## Known limitation

Phase 20 provides the registry and governance contract. It does **not** claim
that any currently registered model is profitable, robust, OOS-validated,
paper-validated, or live-ready.

Those claims require actual evidence from the downstream validation and paper
pipeline.

## Completion gate

Phase 20 is complete only after:

- registry implementation exists;
- deterministic fingerprints are tested;
- artifact identity validation is tested;
- duplicate-version protection is tested;
- lifecycle transitions are tested;
- immutable historical state is tested;
- approval cannot occur without required evidence;
- full repository CI passes;
- documentation is updated;
- no execution/live path is introduced.
