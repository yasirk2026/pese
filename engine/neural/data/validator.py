"""
PESE Neural Genesis: Relation Dataset Validator & Split Integrity Guard
Phase N1: PESE-REL-DATA-0

Strict validation tooling ensuring:
1. Complete scenario-family and source disjointness across splits
2. Entity name disjointness across splits
3. Zero duplicate IDs or (question, evidence) pairs
4. Zero cross-split question or evidence leakage
5. Exact label and negative-reason schema conformance
6. Near-duplicate token overlap auditing
"""

import re
from typing import Dict, List, Set, Tuple, Any, Optional
from collections import defaultdict
from .relation_contracts import RelationExample, RelationLabel, NegativeReason, ContrastType


class DatasetValidationError(Exception):
    """Raised when dataset integrity or split isolation invariants are violated."""
    pass


def normalize_text(text: str) -> str:
    """Normalize text for exact/near-duplicate detection."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(cleaned.split())


def get_tokens(text: str) -> Set[str]:
    """Extract set of normalized word tokens."""
    return set(re.findall(r"\w+", text.lower()))


def token_jaccard(tokens_a: Set[str], tokens_b: Set[str]) -> float:
    """Calculate Jaccard similarity between two token sets."""
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return intersection / union if union > 0 else 0.0


def validate_dataset(
    splits: Dict[str, List[RelationExample]],
    check_entity_disjointness: bool = True
) -> Dict[str, Any]:
    """
    Exhaustively validates a split dictionary (e.g. {'train': [...], 'validation': [...], 'test': [...]}).
    Fails loudly by raising DatasetValidationError if any rule is violated.

    Returns a diagnostic report dictionary when validation passes.
    """
    expected_splits = {"train", "validation", "test"}
    current_splits = set(splits.keys())
    if not current_splits.issubset(expected_splits) or not current_splits:
        raise DatasetValidationError(f"Invalid split keys {current_splits}; expected subset of {expected_splits}")

    seen_ids: Dict[str, str] = {}
    seen_pairs: Dict[Tuple[str, str], str] = {}
    
    split_scenario_families: Dict[str, Set[str]] = defaultdict(set)
    split_source_ids: Dict[str, Set[str]] = defaultdict(set)
    split_entities: Dict[str, Set[str]] = defaultdict(set)
    split_questions: Dict[str, Dict[str, str]] = defaultdict(dict)  # split -> {norm_q: id}
    split_evidences: Dict[str, Dict[str, str]] = defaultdict(dict)  # split -> {norm_e: id}

    counts = {s: len(examples) for s, examples in splits.items()}
    label_counts = {s: {"ANSWERS": 0, "DOES_NOT_ANSWER": 0} for s in splits}
    negative_reasons = {s: defaultdict(int) for s in splits}
    contrast_types = {s: defaultdict(int) for s in splits}
    challenge_counts = {s: 0 for s in splits}

    for split_name, examples in splits.items():
        if not examples:
            raise DatasetValidationError(f"Split '{split_name}' contains zero examples!")

        for idx, ex in enumerate(examples):
            # 1. Missing required fields
            if not ex.id or not ex.id.strip():
                raise DatasetValidationError(f"[{split_name}#{idx}] Missing or empty 'id'")
            if not ex.question or not ex.question.strip():
                raise DatasetValidationError(f"[{split_name}#{idx} id={ex.id}] Missing or empty 'question'")
            if not ex.evidence or not ex.evidence.strip():
                raise DatasetValidationError(f"[{split_name}#{idx} id={ex.id}] Missing or empty 'evidence'")
            if not ex.answer_type or not ex.answer_type.strip():
                raise DatasetValidationError(f"[{split_name}#{idx} id={ex.id}] Missing or empty 'answer_type'")
            if not ex.scenario_family or not ex.scenario_family.strip():
                raise DatasetValidationError(f"[{split_name}#{idx} id={ex.id}] Missing or empty 'scenario_family'")
            if not ex.source_id or not ex.source_id.strip():
                raise DatasetValidationError(f"[{split_name}#{idx} id={ex.id}] Missing or empty 'source_id'")
            if not ex.relation_family or not ex.relation_family.strip():
                raise DatasetValidationError(f"[{split_name}#{idx} id={ex.id}] Missing or empty 'relation_family'")

            # 2. Duplicate ID check
            if ex.id in seen_ids:
                raise DatasetValidationError(
                    f"Duplicate ID '{ex.id}' detected in split '{split_name}'; previously seen in '{seen_ids[ex.id]}'"
                )
            seen_ids[ex.id] = split_name

            # 3. Duplicate (Question, Evidence) pair check
            norm_q = normalize_text(ex.question)
            norm_e = normalize_text(ex.evidence)
            pair_key = (norm_q, norm_e)
            if pair_key in seen_pairs:
                raise DatasetValidationError(
                    f"Duplicate (question, evidence) pair detected for ID '{ex.id}' in '{split_name}'; "
                    f"previously seen in '{seen_pairs[pair_key]}'"
                )
            seen_pairs[pair_key] = f"{split_name}:{ex.id}"

            # 4. Label & Negative Reason consistency
            if ex.label == RelationLabel.ANSWERS:
                label_counts[split_name]["ANSWERS"] += 1
                if ex.negative_reason is not None:
                    raise DatasetValidationError(
                        f"Example '{ex.id}' has label ANSWERS but non-null negative_reason '{ex.negative_reason}'"
                    )
            elif ex.label == RelationLabel.DOES_NOT_ANSWER:
                label_counts[split_name]["DOES_NOT_ANSWER"] += 1
                if ex.negative_reason is None:
                    raise DatasetValidationError(
                        f"Example '{ex.id}' has label DOES_NOT_ANSWER but negative_reason is None"
                    )
                negative_reasons[split_name][ex.negative_reason.value] += 1
            else:
                raise DatasetValidationError(f"Example '{ex.id}' has invalid label '{ex.label}'")

            if ex.contrast_type is not None:
                contrast_types[split_name][ex.contrast_type.value] += 1

            if ex.is_challenge:
                challenge_counts[split_name] += 1

            # Accumulate split partition keys
            split_scenario_families[split_name].add(ex.scenario_family)
            split_source_ids[split_name].add(ex.source_id)
            for ent in ex.entities:
                cleaned_ent = ent.strip().lower()
                if cleaned_ent:
                    split_entities[split_name].add(cleaned_ent)

            split_questions[split_name][norm_q] = ex.id
            split_evidences[split_name][norm_e] = ex.id

    # 5. Cross-split Leakage Checks
    split_names = list(splits.keys())
    for i in range(len(split_names)):
        for j in range(i + 1, len(split_names)):
            s1, s2 = split_names[i], split_names[j]

            # Scenario family leakage
            leak_scenarios = split_scenario_families[s1] & split_scenario_families[s2]
            if leak_scenarios:
                raise DatasetValidationError(
                    f"Scenario family leakage between '{s1}' and '{s2}': {leak_scenarios}"
                )

            # Source ID leakage
            leak_sources = split_source_ids[s1] & split_source_ids[s2]
            if leak_sources:
                raise DatasetValidationError(
                    f"Source ID leakage between '{s1}' and '{s2}': {leak_sources}"
                )

            # Entity leakage (if enabled)
            if check_entity_disjointness:
                leak_entities = split_entities[s1] & split_entities[s2]
                if leak_entities:
                    raise DatasetValidationError(
                        f"Entity name leakage between '{s1}' and '{s2}': {leak_entities}"
                    )

            # Exact question leakage
            common_questions = set(split_questions[s1].keys()) & set(split_questions[s2].keys())
            if common_questions:
                sample_q = next(iter(common_questions))
                id1 = split_questions[s1][sample_q]
                id2 = split_questions[s2][sample_q]
                raise DatasetValidationError(
                    f"Exact question leakage between '{s1}' ({id1}) and '{s2}' ({id2}): '{sample_q}'"
                )

            # Exact evidence leakage
            common_evidences = set(split_evidences[s1].keys()) & set(split_evidences[s2].keys())
            if common_evidences:
                sample_e = next(iter(common_evidences))
                id1 = split_evidences[s1][sample_e]
                id2 = split_evidences[s2][sample_e]
                raise DatasetValidationError(
                    f"Exact evidence leakage between '{s1}' ({id1}) and '{s2}' ({id2}): '{sample_e}'"
                )

    return {
        "valid": True,
        "total_examples": sum(counts.values()),
        "split_counts": counts,
        "label_counts": label_counts,
        "challenge_counts": challenge_counts,
        "scenario_family_counts": {s: len(fams) for s, fams in split_scenario_families.items()},
        "source_id_counts": {s: len(srcs) for s, srcs in split_source_ids.items()},
        "entity_counts": {s: len(ents) for s, ents in split_entities.items()},
        "negative_reasons": {s: dict(nr) for s, nr in negative_reasons.items()},
        "contrast_types": {s: dict(ct) for s, ct in contrast_types.items()},
    }


def audit_near_duplicates(
    splits: Dict[str, List[RelationExample]],
    jaccard_threshold: float = 0.85
) -> List[Dict[str, Any]]:
    """
    Scans across split boundaries for suspicious near-duplicate questions or evidence passages.
    Returns a list of flagged near-duplicate pairs for human or QA review.
    Does NOT silently delete data.
    """
    flagged: List[Dict[str, Any]] = []
    split_names = list(splits.keys())

    for i in range(len(split_names)):
        for j in range(i + 1, len(split_names)):
            s1, s2 = split_names[i], split_names[j]
            list1 = splits[s1]
            list2 = splits[s2]

            for ex1 in list1:
                tokens_q1 = get_tokens(ex1.question)
                tokens_e1 = get_tokens(ex1.evidence)

                for ex2 in list2:
                    tokens_q2 = get_tokens(ex2.question)
                    sim_q = token_jaccard(tokens_q1, tokens_q2)
                    if sim_q >= jaccard_threshold:
                        flagged.append({
                            "type": "NEAR_DUPLICATE_QUESTION",
                            "similarity": round(sim_q, 4),
                            "split_a": s1,
                            "id_a": ex1.id,
                            "text_a": ex1.question,
                            "split_b": s2,
                            "id_b": ex2.id,
                            "text_b": ex2.question,
                        })

                    tokens_e2 = get_tokens(ex2.evidence)
                    sim_e = token_jaccard(tokens_e1, tokens_e2)
                    if sim_e >= jaccard_threshold:
                        flagged.append({
                            "type": "NEAR_DUPLICATE_EVIDENCE",
                            "similarity": round(sim_e, 4),
                            "split_a": s1,
                            "id_a": ex1.id,
                            "text_a": ex1.evidence,
                            "split_b": s2,
                            "id_b": ex2.id,
                            "text_b": ex2.evidence,
                        })

    return flagged
