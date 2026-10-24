"""
PESE Neural Genesis: Relation Reasoning Data Contracts & Schemas
Phase N1: PESE-REL-DATA-0

Defines the core data contract for relational answer-support judgments:
Given (Question, Candidate Evidence Passage/Sentence), determine whether
the evidence genuinely ANSWERS the question (ANSWERS vs DOES_NOT_ANSWER).

Strictly decoupled from search ranking, generative rewriting, and private corpora.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class RelationLabel(str, Enum):
    """
    Core binary target labels for PESE-Rel relation reasoning.
    ANSWERS: Contains evidence that directly resolves/answers the question.
    DOES_NOT_ANSWER: Merely same topic, wrong relation, wrong entity, or distractor.
    """
    ANSWERS = "ANSWERS"
    DOES_NOT_ANSWER = "DOES_NOT_ANSWER"


class NegativeReason(str, Enum):
    """
    Diagnostic negative metadata for post-hoc error analysis.
    These are analytical tags, NOT multi-class training targets.
    """
    WRONG_ENTITY = "WRONG_ENTITY"
    WRONG_PREDICATE = "WRONG_PREDICATE"
    WRONG_PROPERTY = "WRONG_PROPERTY"
    WRONG_ANSWER_TYPE = "WRONG_ANSWER_TYPE"
    SAME_TOPIC_WRONG_RELATION = "SAME_TOPIC_WRONG_RELATION"
    NEGATION_CONFLICT = "NEGATION_CONFLICT"
    MISSING_INFORMATION = "MISSING_INFORMATION"
    RELATED_EVENT = "RELATED_EVENT"
    QUESTION_RESTATEMENT = "QUESTION_RESTATEMENT"
    EXPLICIT_UNKNOWN = "EXPLICIT_UNKNOWN"
    ENTITY_CONFUSION = "ENTITY_CONFUSION"
    PREDICATE_CONFUSION = "PREDICATE_CONFUSION"
    HIGH_OVERLAP_DISTRACTOR = "HIGH_OVERLAP_DISTRACTOR"
    EASY_UNRELATED = "EASY_UNRELATED"


class ContrastType(str, Enum):
    """
    Contrastive relationship category for training curriculum and hard evaluations.
    """
    ENTITY_CONTRAST = "ENTITY_CONTRAST"
    ENTITY_VERSION_CONTRAST = "ENTITY_VERSION_CONTRAST"
    ATTRIBUTE_CONTRAST = "ATTRIBUTE_CONTRAST"
    TEMPORAL_CONTRAST = "TEMPORAL_CONTRAST"
    PERSON_ROLE_CONTRAST = "PERSON_ROLE_CONTRAST"
    CAUSAL_CONTRAST = "CAUSAL_CONTRAST"
    BOOLEAN_NEGATION_CONTRAST = "BOOLEAN_NEGATION_CONTRAST"
    EXPLICIT_UNKNOWN_CONTRAST = "EXPLICIT_UNKNOWN_CONTRAST"
    DEFINITION_CONTRAST = "DEFINITION_CONTRAST"
    PROCEDURAL_CONTRAST = "PROCEDURAL_CONTRAST"
    COMPARISON_CONTRAST = "COMPARISON_CONTRAST"
    PARAPHRASE_LOW_OVERLAP = "PARAPHRASE_LOW_OVERLAP"
    HIGH_OVERLAP_DISTRACTOR = "HIGH_OVERLAP_DISTRACTOR"
    QUESTION_REPETITION = "QUESTION_REPETITION"
    SAME_TOPIC_WRONG_RELATION = "SAME_TOPIC_WRONG_RELATION"
    DIRECT_FACTUAL = "DIRECT_FACTUAL"


class RelationExample(BaseModel):
    """
    Single relational training / evaluation instance for PESE-Rel models.
    """
    id: str = Field(..., description="Globally unique example identifier (e.g. 'rel-0001')")
    question: str = Field(..., description="Target question text")
    evidence: str = Field(..., description="Candidate sentence or short passage to be evaluated")
    label: RelationLabel = Field(..., description="Binary relation truth label: ANSWERS or DOES_NOT_ANSWER")
    answer_type: str = Field(..., description="Expected answer semantic type (e.g. PERSON, DATE, NUMBER, BOOLEAN, DEFINITION, PROCEDURE)")
    scenario_family: str = Field(..., description="Scenario family cluster; strictly disjoint across train/val/test splits")
    source_id: str = Field(..., description="Synthetic document or scenario source identifier; strictly disjoint across splits")
    relation_family: str = Field(..., description="Predicate or relation family (e.g. 'repair_actor', 'operating_frequency', 'founding_date')")
    difficulty: str = Field(default="direct", description="Difficulty tier: 'direct', 'contrastive', 'hard_negative', 'low_overlap_positive', 'easy_distractor'")
    negative_reason: Optional[NegativeReason] = Field(default=None, description="Diagnostic negative metadata; strictly None for ANSWERS")
    contrast_type: Optional[ContrastType] = Field(default=None, description="Specific contrastive pattern represented by this pair")
    is_challenge: bool = Field(default=False, description="Flag indicating membership in the hard challenge evaluation subset")
    entities: List[str] = Field(default_factory=list, description="Named entities referenced in this scenario; verified disjoint across splits")
    notes: Optional[str] = Field(default=None, description="Optional engineering commentary or design notes")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary extension metadata")

    def model_dump_clean(self) -> Dict[str, Any]:
        """Produce a clean JSON-serializable dictionary representation."""
        data = self.model_dump()
        data["label"] = self.label.value
        if self.negative_reason is not None:
            data["negative_reason"] = self.negative_reason.value
        if self.contrast_type is not None:
            data["contrast_type"] = self.contrast_type.value
        return data
