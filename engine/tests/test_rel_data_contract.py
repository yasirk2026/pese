"""
PESE Unit Tests: Relation Reasoning Data Contract & Dataset Validator
Phase N1: PESE-REL-DATA-0 Integrity Tests
"""

import pytest
import copy
from engine.neural.data.relation_contracts import (
    RelationExample,
    RelationLabel,
    NegativeReason,
    ContrastType
)
from engine.neural.data.validator import (
    validate_dataset,
    audit_near_duplicates,
    DatasetValidationError
)
from engine.neural.data.manifest import load_frozen_dataset
from engine.neural.models.relation_model_design import PESERelationConfig


@pytest.fixture
def clean_dummy_split():
    """Generates a minimal valid disjoint split."""
    train = [
        RelationExample(
            id="dummy-tr-1",
            question="Who repaired the bicycle?",
            evidence="Amina repaired the bicycle.",
            label=RelationLabel.ANSWERS,
            answer_type="PERSON",
            scenario_family="bicycle_repair_train",
            source_id="synth_bicycle_01",
            relation_family="repair_actor",
            entities=["Amina", "bicycle"]
        ),
        RelationExample(
            id="dummy-tr-2",
            question="Who repaired the bicycle?",
            evidence="The bicycle was manufactured in 1990.",
            label=RelationLabel.DOES_NOT_ANSWER,
            answer_type="PERSON",
            scenario_family="bicycle_repair_train",
            source_id="synth_bicycle_01",
            relation_family="repair_actor",
            negative_reason=NegativeReason.SAME_TOPIC_WRONG_RELATION,
            entities=["Amina", "bicycle"]
        )
    ]
    val = [
        RelationExample(
            id="dummy-val-1",
            question="When was the clock built?",
            evidence="Elena constructed the clock in 1910.",
            label=RelationLabel.ANSWERS,
            answer_type="DATE",
            scenario_family="clock_history_val",
            source_id="synth_clock_02",
            relation_family="build_date",
            entities=["Elena", "clock"]
        ),
        RelationExample(
            id="dummy-val-2",
            question="When was the clock built?",
            evidence="Marcus wound the clock weights.",
            label=RelationLabel.DOES_NOT_ANSWER,
            answer_type="DATE",
            scenario_family="clock_history_val",
            source_id="synth_clock_02",
            relation_family="build_date",
            negative_reason=NegativeReason.WRONG_PREDICATE,
            entities=["Marcus", "clock"]
        )
    ]
    test = [
        RelationExample(
            id="dummy-te-1",
            question="What is the speed of the glider?",
            evidence="The glider flies at 45 km/h.",
            label=RelationLabel.ANSWERS,
            answer_type="SPEED",
            scenario_family="glider_aero_test",
            source_id="synth_glider_03",
            relation_family="flight_speed",
            entities=["glider"]
        ),
        RelationExample(
            id="dummy-te-2",
            question="What is the speed of the glider?",
            evidence="Soren built the glider wings from pine.",
            label=RelationLabel.DOES_NOT_ANSWER,
            answer_type="SPEED",
            scenario_family="glider_aero_test",
            source_id="synth_glider_03",
            relation_family="flight_speed",
            negative_reason=NegativeReason.WRONG_PROPERTY,
            entities=["Soren", "glider"]
        )
    ]
    return {"train": train, "validation": val, "test": test}


def test_relation_example_schema_and_serialization():
    ex = RelationExample(
        id="rel-test-001",
        question="Who built the aqueduct?",
        evidence="Masons built the aqueduct in 840 CE.",
        label=RelationLabel.ANSWERS,
        answer_type="PERSON",
        scenario_family="aqueduct_01",
        source_id="synth_source_01",
        relation_family="construction_actor",
        difficulty="direct",
        contrast_type=ContrastType.DIRECT_FACTUAL,
        entities=["Masons", "aqueduct"]
    )
    clean_dict = ex.model_dump_clean()
    assert clean_dict["label"] == "ANSWERS"
    assert clean_dict["contrast_type"] == "DIRECT_FACTUAL"
    assert clean_dict["negative_reason"] is None


def test_validator_passes_valid_split(clean_dummy_split):
    report = validate_dataset(clean_dummy_split, check_entity_disjointness=False)
    assert report["valid"] is True
    assert report["total_examples"] == 6


def test_validator_detects_duplicate_id(clean_dummy_split):
    bad_split = copy.deepcopy(clean_dummy_split)
    bad_split["test"][0].id = bad_split["train"][0].id
    with pytest.raises(DatasetValidationError, match="Duplicate ID"):
        validate_dataset(bad_split, check_entity_disjointness=False)


def test_validator_detects_duplicate_pair(clean_dummy_split):
    bad_split = copy.deepcopy(clean_dummy_split)
    bad_split["test"][0].question = bad_split["train"][0].question
    bad_split["test"][0].evidence = bad_split["train"][0].evidence
    with pytest.raises(DatasetValidationError, match="Duplicate \\(question, evidence\\) pair"):
        validate_dataset(bad_split, check_entity_disjointness=False)


def test_validator_detects_scenario_family_leakage(clean_dummy_split):
    bad_split = copy.deepcopy(clean_dummy_split)
    bad_split["validation"][0].scenario_family = bad_split["train"][0].scenario_family
    with pytest.raises(DatasetValidationError, match="Scenario family leakage"):
        validate_dataset(bad_split, check_entity_disjointness=False)


def test_validator_detects_source_id_leakage(clean_dummy_split):
    bad_split = copy.deepcopy(clean_dummy_split)
    bad_split["test"][0].source_id = bad_split["train"][0].source_id
    with pytest.raises(DatasetValidationError, match="Source ID leakage"):
        validate_dataset(bad_split, check_entity_disjointness=False)


def test_validator_detects_entity_leakage(clean_dummy_split):
    bad_split = copy.deepcopy(clean_dummy_split)
    bad_split["test"][0].entities = ["Amina"]  # Amina is in train
    with pytest.raises(DatasetValidationError, match="Entity name leakage"):
        validate_dataset(bad_split, check_entity_disjointness=True)


def test_validator_detects_exact_question_leakage(clean_dummy_split):
    bad_split = copy.deepcopy(clean_dummy_split)
    bad_split["validation"][0].question = bad_split["train"][0].question
    with pytest.raises(DatasetValidationError, match="Exact question leakage"):
        validate_dataset(bad_split, check_entity_disjointness=False)


def test_validator_detects_exact_evidence_leakage(clean_dummy_split):
    bad_split = copy.deepcopy(clean_dummy_split)
    bad_split["validation"][0].evidence = bad_split["train"][0].evidence
    with pytest.raises(DatasetValidationError, match="Exact evidence leakage"):
        validate_dataset(bad_split, check_entity_disjointness=False)


def test_validator_enforces_negative_reason_consistency(clean_dummy_split):
    bad_split = copy.deepcopy(clean_dummy_split)
    # DOES_NOT_ANSWER without negative reason
    bad_split["train"][1].negative_reason = None
    with pytest.raises(DatasetValidationError, match="negative_reason is None"):
        validate_dataset(bad_split, check_entity_disjointness=False)

    # ANSWERS with negative reason
    bad_split = copy.deepcopy(clean_dummy_split)
    bad_split["train"][0].negative_reason = NegativeReason.WRONG_ENTITY
    with pytest.raises(DatasetValidationError, match="non-null negative_reason"):
        validate_dataset(bad_split, check_entity_disjointness=False)


def test_near_duplicate_audit():
    ex1 = RelationExample(
        id="a1", question="Who repaired the church clock in the tower?",
        evidence="Nadia repaired it.", label=RelationLabel.ANSWERS,
        answer_type="PERSON", scenario_family="f1", source_id="s1", relation_family="r1"
    )
    ex2 = RelationExample(
        id="b1", question="Who repaired the church clock in the stone tower?",
        evidence="Elena fixed it.", label=RelationLabel.ANSWERS,
        answer_type="PERSON", scenario_family="f2", source_id="s2", relation_family="r2"
    )
    splits = {"train": [ex1], "validation": [ex2]}
    flagged = audit_near_duplicates(splits, jaccard_threshold=0.75)
    assert len(flagged) >= 1
    assert flagged[0]["type"] == "NEAR_DUPLICATE_QUESTION"


def test_frozen_dataset_loads_and_verifies():
    splits = load_frozen_dataset()
    assert "train" in splits
    assert "validation" in splits
    assert "test" in splits
    assert len(splits["train"]) == 480
    assert len(splits["validation"]) == 120
    assert len(splits["test"]) == 120
    assert sum(len(v) for v in splits.values()) == 720


def test_future_model_config_parameters():
    cfg = PESERelationConfig()
    params = cfg.count_parameters()
    assert 800_000 < params < 1_000_000
    assert cfg.d_model == 128
    assert cfg.n_layers == 4
