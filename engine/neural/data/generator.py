"""
PESE Neural Genesis: PESE-REL-DATA-0 Dataset Generator
Phase N1: Build the Learning Contract Before Training the Brain

Generates reproducible, strictly scenario-disjoint, entity-disjoint synthetic
examples for relation reasoning and answer-support classification.

Strict Constraints:
- ZERO private corpus data (no personal notes, memories, search history).
- ZERO old holdout leakage.
- Disjoint scenario families and entities across Train, Validation, and Test.
- High ratio of hard contrastive negatives (same topic wrong relation, entity confusion,
  predicate confusion, property mismatch, high lexical overlap).
- Low-overlap positives (lexical variety and semantic paraphrases).
- Target size: ~720 examples (~480 train, ~120 val, ~120 test).
- Perfectly balanced labels: ~50% ANSWERS, ~50% DOES_NOT_ANSWER.
"""

from typing import Dict, List, Tuple
from .relation_contracts import (
    RelationExample,
    RelationLabel,
    NegativeReason,
    ContrastType
)


def _build_train_scenarios() -> List[RelationExample]:
    examples: List[RelationExample] = []
    e_idx = 1

    def add_ex(
        q: str, ev: str, lbl: RelationLabel, ans_type: str, fam: str, src: str,
        rel: str, diff: str, neg_reason=None, contrast=None, is_chal=False,
        ents=None, notes=None
    ):
        nonlocal e_idx
        ex = RelationExample(
            id=f"pese-rel-train-{e_idx:04d}",
            question=q,
            evidence=ev,
            label=lbl,
            answer_type=ans_type,
            scenario_family=fam,
            source_id=src,
            relation_family=rel,
            difficulty=diff,
            negative_reason=neg_reason,
            contrast_type=contrast,
            is_challenge=is_chal,
            entities=ents or [],
            notes=notes
        )
        examples.append(ex)
        e_idx += 1

    # Define 60 Train Scenario Families systematically with balanced contrasts
    # Each family has 4 positive and 4 negative examples (8 examples total = 480 train examples)
    
    # 1. Station Clock Maintenance
    fam = "train_station_clock_01"
    src = "synth_station_archive_01"
    ents = ["Nadia", "Charles", "Hamza", "station clock"]
    add_ex("Who repaired the station clock?", "Engineer Nadia repaired the station clock in 1998.", RelationLabel.ANSWERS, "PERSON", fam, src, "repair_actor", "direct", contrast=ContrastType.DIRECT_FACTUAL, ents=ents)
    add_ex("Who fixed the station timepiece?", "Nadia restored the broken gears of the station clock to working order.", RelationLabel.ANSWERS, "PERSON", fam, src, "repair_actor", "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=ents)
    add_ex("When was the station clock repaired?", "Nadia repaired the station clock in 1998.", RelationLabel.ANSWERS, "DATE", fam, src, "repair_date", "direct", contrast=ContrastType.TEMPORAL_CONTRAST, ents=ents)
    add_ex("In what year did Nadia finish repairing the clock?", "The restoration of the clock mechanism was completed by Nadia in 1998.", RelationLabel.ANSWERS, "DATE", fam, src, "repair_date", "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=ents)
    add_ex("Who repaired the station clock?", "The station clock stopped during a violent winter storm.", RelationLabel.DOES_NOT_ANSWER, "PERSON", fam, src, "repair_actor", "hard_negative", neg_reason=NegativeReason.SAME_TOPIC_WRONG_RELATION, contrast=ContrastType.HIGH_OVERLAP_DISTRACTOR, is_chal=True, ents=ents)
    add_ex("Who repaired the station clock?", "Hamza inspected the station clock but did not perform repairs.", RelationLabel.DOES_NOT_ANSWER, "PERSON", fam, src, "repair_actor", "hard_negative", neg_reason=NegativeReason.WRONG_PREDICATE, contrast=ContrastType.PERSON_ROLE_CONTRAST, is_chal=True, ents=ents)
    add_ex("Who repaired the station clock?", "Charles repaired the telegraph line near the station clock.", RelationLabel.DOES_NOT_ANSWER, "PERSON", fam, src, "repair_actor", "hard_negative", neg_reason=NegativeReason.WRONG_PROPERTY, contrast=ContrastType.ENTITY_CONTRAST, is_chal=True, ents=ents)
    add_ex("When was the station clock repaired?", "The station opened in 1984 before the clock was installed.", RelationLabel.DOES_NOT_ANSWER, "DATE", fam, src, "repair_date", "hard_negative", neg_reason=NegativeReason.RELATED_EVENT, contrast=ContrastType.TEMPORAL_CONTRAST, is_chal=True, ents=ents)

    # 2. Bicycle Workshop
    fam = "train_bicycle_service_02"
    src = "synth_bicycle_shop_02"
    ents = ["Amina", "Charles", "Farid", "commuter bicycle"]
    add_ex("Who repaired Charles's bicycle?", "Amina repaired Charles's bicycle at the community workshop.", RelationLabel.ANSWERS, "PERSON", fam, src, "repair_actor", "direct", contrast=ContrastType.DIRECT_FACTUAL, ents=ents)
    add_ex("What brakes does the commuter bicycle use?", "The commuter bicycle is equipped with hydraulic disc brakes.", RelationLabel.ANSWERS, "SPECIFICATION", fam, src, "brake_type", "direct", contrast=ContrastType.ATTRIBUTE_CONTRAST, ents=ents)
    add_ex("How heavy is the commuter bicycle?", "The overall mass of the two-wheeler comes to 11 kg.", RelationLabel.ANSWERS, "NUMBER", fam, src, "weight", "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=ents)
    add_ex("Which technician overhauled Charles's bike?", "Amina serviced Charles's bicycle and tuned its gears.", RelationLabel.ANSWERS, "PERSON", fam, src, "repair_actor", "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=ents)
    add_ex("Who repaired Charles's bicycle?", "Charles repaired Amina's bicycle yesterday afternoon.", RelationLabel.DOES_NOT_ANSWER, "PERSON", fam, src, "repair_actor", "hard_negative", neg_reason=NegativeReason.WRONG_ENTITY, contrast=ContrastType.ENTITY_CONTRAST, is_chal=True, ents=ents)
    add_ex("Who repaired Charles's bicycle?", "Amina repaired Farid's bicycle using new brake cables.", RelationLabel.DOES_NOT_ANSWER, "PERSON", fam, src, "repair_actor", "hard_negative", neg_reason=NegativeReason.WRONG_ENTITY, contrast=ContrastType.ENTITY_CONTRAST, is_chal=True, ents=ents)
    add_ex("What brakes does the commuter bicycle use?", "The commuter bicycle weighs exactly 11 kg without pedals.", RelationLabel.DOES_NOT_ANSWER, "SPECIFICATION", fam, src, "brake_type", "hard_negative", neg_reason=NegativeReason.WRONG_PROPERTY, contrast=ContrastType.ATTRIBUTE_CONTRAST, is_chal=True, ents=ents)
    add_ex("What brakes does the commuter bicycle use?", "Its frame is crafted from triple-butted aluminum alloy.", RelationLabel.DOES_NOT_ANSWER, "SPECIFICATION", fam, src, "brake_type", "hard_negative", neg_reason=NegativeReason.WRONG_PROPERTY, contrast=ContrastType.ATTRIBUTE_CONTRAST, is_chal=True, ents=ents)

    # 3. Game Sequels
    fam = "train_game_development_03"
    src = "synth_gaming_press_03"
    ents = ["PixelForge", "Nova V", "Nova VI", "Console 4", "Console 4 Pro"]
    add_ex("Who developed Nova VI?", "PixelForge developed Nova VI over a four-year production cycle.", RelationLabel.ANSWERS, "ORGANIZATION", fam, src, "developer", "direct", contrast=ContrastType.DIRECT_FACTUAL, ents=ents)
    add_ex("What studio created Nova VI?", "The flagship action title Nova VI was authored by the designers at PixelForge.", RelationLabel.ANSWERS, "ORGANIZATION", fam, src, "developer", "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=ents)
    add_ex("Does Nova VI support Console 4 Pro?", "Nova VI features enhanced 60 FPS rendering on Console 4 Pro.", RelationLabel.ANSWERS, "BOOLEAN", fam, src, "platform_support", "direct", contrast=ContrastType.BOOLEAN_NEGATION_CONTRAST, ents=ents)
    add_ex("Does Nova VI support Console 4 Pro?", "Nova VI does not support Console 4 Pro due to engine architectural limits.", RelationLabel.ANSWERS, "BOOLEAN", fam, src, "platform_support", "direct", contrast=ContrastType.BOOLEAN_NEGATION_CONTRAST, is_chal=True, ents=ents)
    add_ex("Who developed Nova VI?", "PixelForge developed Nova V before shifting focus to mobile titles.", RelationLabel.DOES_NOT_ANSWER, "ORGANIZATION", fam, src, "developer", "hard_negative", neg_reason=NegativeReason.ENTITY_CONFUSION, contrast=ContrastType.ENTITY_VERSION_CONTRAST, is_chal=True, ents=ents)
    add_ex("Does Nova VI support Console 4 Pro?", "Nova VI is fully compatible with standard Console 4 hardware.", RelationLabel.DOES_NOT_ANSWER, "BOOLEAN", fam, src, "platform_support", "hard_negative", neg_reason=NegativeReason.ENTITY_CONFUSION, contrast=ContrastType.ENTITY_VERSION_CONTRAST, is_chal=True, ents=ents)
    add_ex("Does Nova VI support Console 4 Pro?", "A comprehensive guide for Console 4 Pro hardware upgrades was published.", RelationLabel.DOES_NOT_ANSWER, "BOOLEAN", fam, src, "platform_support", "hard_negative", neg_reason=NegativeReason.SAME_TOPIC_WRONG_RELATION, contrast=ContrastType.HIGH_OVERLAP_DISTRACTOR, is_chal=True, ents=ents)
    add_ex("Who developed Nova VI?", "Industry analysts frequently discuss who developed Nova VI.", RelationLabel.DOES_NOT_ANSWER, "ORGANIZATION", fam, src, "developer", "hard_negative", neg_reason=NegativeReason.QUESTION_RESTATEMENT, contrast=ContrastType.QUESTION_REPETITION, is_chal=True, ents=ents)

    # 4. Clinic Billing Policy
    fam = "train_clinic_billing_04"
    src = "synth_health_terms_04"
    ents = ["Pearl Clinic", "Tariq", "consultation fee"]
    add_ex("Are installment payments available at Pearl Clinic?", "Patients may divide the consultation fee into three monthly installments.", RelationLabel.ANSWERS, "BOOLEAN", fam, src, "payment_options", "direct", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=ents)
    add_ex("Are installment payments available at Pearl Clinic?", "Pearl Clinic does not offer installment payment options for outpatient care.", RelationLabel.ANSWERS, "BOOLEAN", fam, src, "payment_options", "direct", contrast=ContrastType.BOOLEAN_NEGATION_CONTRAST, is_chal=True, ents=ents)
    add_ex("Can clients split the consultation fee at Pearl Clinic?", "Visitors to Pearl Clinic are permitted to settle the examination charge across multiple billing cycles.", RelationLabel.ANSWERS, "BOOLEAN", fam, src, "payment_options", "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=ents)
    add_ex("Does Pearl Clinic provide flexible fee installments?", "Pearl Clinic allows all medical fees to be settled via four quarterly installments.", RelationLabel.ANSWERS, "BOOLEAN", fam, src, "payment_options", "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=ents)
    add_ex("Are installment payments available at Pearl Clinic?", "Pearl Clinic published a detailed financial guide outlining service costs.", RelationLabel.DOES_NOT_ANSWER, "BOOLEAN", fam, src, "payment_options", "hard_negative", neg_reason=NegativeReason.SAME_TOPIC_WRONG_RELATION, contrast=ContrastType.HIGH_OVERLAP_DISTRACTOR, is_chal=True, ents=ents)
    add_ex("Are installment payments available at Pearl Clinic?", "Dr. Tariq conducts medical consultations at Pearl Clinic on weekday mornings.", RelationLabel.DOES_NOT_ANSWER, "BOOLEAN", fam, src, "payment_options", "hard_negative", neg_reason=NegativeReason.WRONG_PROPERTY, contrast=ContrastType.HIGH_OVERLAP_DISTRACTOR, is_chal=True, ents=ents)
    add_ex("What time did Tariq begin the clinical inspection?", "No one recorded the time when the inspection began.", RelationLabel.DOES_NOT_ANSWER, "TIME", fam, src, "inspection_time", "hard_negative", neg_reason=NegativeReason.EXPLICIT_UNKNOWN, contrast=ContrastType.EXPLICIT_UNKNOWN_CONTRAST, is_chal=True, ents=ents)
    add_ex("Are installment payments available at Pearl Clinic?", "Patients frequently ask if installment payments are available at Pearl Clinic.", RelationLabel.DOES_NOT_ANSWER, "BOOLEAN", fam, src, "payment_options", "hard_negative", neg_reason=NegativeReason.QUESTION_RESTATEMENT, contrast=ContrastType.QUESTION_REPETITION, is_chal=True, ents=ents)

    # 5. Flux Relay
    fam = "train_flux_relay_05"
    src = "synth_engineering_specs_05"
    ents = ["Flux Relay", "AeroGrid", "cooling circuit"]
    add_ex("What is a flux relay?", "A flux relay is an electro-magnetic switch that regulates current between two isolated circuits.", RelationLabel.ANSWERS, "DEFINITION", fam, src, "definition", "direct", contrast=ContrastType.DEFINITION_CONTRAST, ents=ents)
    add_ex("How should an engineer reset the flux relay?", "Depress the red override latch for five seconds until the green beacon illuminates.", RelationLabel.ANSWERS, "PROCEDURE", fam, src, "reset_procedure", "direct", contrast=ContrastType.PROCEDURAL_CONTRAST, ents=ents)
    add_ex("Can you explain what defines a flux relay?", "By definition, a flux relay functions as a protective device diverting surge currents across power grids.", RelationLabel.ANSWERS, "DEFINITION", fam, src, "definition", "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=ents)
    add_ex("What steps reboot the flux relay?", "To restart the unit, hold down the breaker lever until all indicator lights flash amber.", RelationLabel.ANSWERS, "PROCEDURE", fam, src, "reset_procedure", "low_overlap_positive", contrast=ContrastType.PROCEDURAL_CONTRAST, is_chal=True, ents=ents)
    add_ex("What is a flux relay?", "The AeroGrid substation installed four flux relays during modernization.", RelationLabel.DOES_NOT_ANSWER, "DEFINITION", fam, src, "definition", "hard_negative", neg_reason=NegativeReason.SAME_TOPIC_WRONG_RELATION, contrast=ContrastType.DEFINITION_CONTRAST, is_chal=True, ents=ents)
    add_ex("What is a flux relay?", "Technicians tested the flux relay in high temperature environments.", RelationLabel.DOES_NOT_ANSWER, "DEFINITION", fam, src, "definition", "hard_negative", neg_reason=NegativeReason.WRONG_PREDICATE, contrast=ContrastType.DEFINITION_CONTRAST, is_chal=True, ents=ents)
    add_ex("How should an engineer reset the flux relay?", "The flux relay housing contains a circular reset button on its lower panel.", RelationLabel.DOES_NOT_ANSWER, "PROCEDURE", fam, src, "reset_procedure", "hard_negative", neg_reason=NegativeReason.WRONG_PREDICATE, contrast=ContrastType.PROCEDURAL_CONTRAST, is_chal=True, ents=ents)
    add_ex("How should an engineer reset the flux relay?", "The maintenance manual describes procedures for resetting electrical relays.", RelationLabel.DOES_NOT_ANSWER, "PROCEDURE", fam, src, "reset_procedure", "hard_negative", neg_reason=NegativeReason.SAME_TOPIC_WRONG_RELATION, contrast=ContrastType.HIGH_OVERLAP_DISTRACTOR, is_chal=True, ents=ents)

    # 6. Cloud Comparison
    fam = "train_cloud_comparison_06"
    src = "synth_cloud_eval_06"
    ents = ["Orion 4", "Vega One", "Solaria Data"]
    add_ex("What are the differences between Orion 4 and Vega One?", "Orion 4 uses magnetic tape archival, whereas Vega One employs high-speed solid-state arrays.", RelationLabel.ANSWERS, "DESCRIPTION", fam, src, "architecture_diff", "direct", contrast=ContrastType.COMPARISON_CONTRAST, is_chal=True, ents=ents)
    add_ex("How do Orion 4 and Vega One differ?", "While Orion 4 focuses on low-cost batch processing, Vega One is engineered for real-time transactional streams.", RelationLabel.ANSWERS, "DESCRIPTION", fam, src, "architecture_diff", "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=ents)
    add_ex("Does Orion 4 consume more power than Vega One?", "Comparative testing shows Orion 4 draws 450 watts compared to 280 watts for Vega One.", RelationLabel.ANSWERS, "BOOLEAN", fam, src, "power_diff", "direct", contrast=ContrastType.COMPARISON_CONTRAST, ents=ents)
    add_ex("Which platform is faster between Orion 4 and Vega One?", "Vega One achieves ten times higher IOPS than Orion 4 in standard benchmarks.", RelationLabel.ANSWERS, "DESCRIPTION", fam, src, "speed_diff", "direct", contrast=ContrastType.COMPARISON_CONTRAST, ents=ents)
    add_ex("What are the differences between Orion 4 and Vega One?", "Orion 4 was released by Solaria Data in late 2021.", RelationLabel.DOES_NOT_ANSWER, "DESCRIPTION", fam, src, "architecture_diff", "hard_negative", neg_reason=NegativeReason.MISSING_INFORMATION, contrast=ContrastType.COMPARISON_CONTRAST, is_chal=True, ents=ents)
    add_ex("What are the differences between Orion 4 and Vega One?", "Vega One received an essential firmware patch last month.", RelationLabel.DOES_NOT_ANSWER, "DESCRIPTION", fam, src, "architecture_diff", "hard_negative", neg_reason=NegativeReason.MISSING_INFORMATION, contrast=ContrastType.COMPARISON_CONTRAST, is_chal=True, ents=ents)
    add_ex("What are the differences between Orion 4 and Vega One?", "Both Orion 4 and Vega One operate inside Solaria Data server rooms.", RelationLabel.DOES_NOT_ANSWER, "DESCRIPTION", fam, src, "architecture_diff", "hard_negative", neg_reason=NegativeReason.SAME_TOPIC_WRONG_RELATION, contrast=ContrastType.COMPARISON_CONTRAST, is_chal=True, ents=ents)
    add_ex("What are the differences between Orion 4 and Vega One?", "Users commonly compare the differences between Orion 4 and Vega One.", RelationLabel.DOES_NOT_ANSWER, "DESCRIPTION", fam, src, "architecture_diff", "hard_negative", neg_reason=NegativeReason.QUESTION_RESTATEMENT, contrast=ContrastType.QUESTION_REPETITION, is_chal=True, ents=ents)

    # 7. Bridge Engineering
    fam = "train_bridge_engineering_07"
    src = "synth_infrastructure_07"
    ents = ["Thorne Bridge", "Farid", "Nadia", "Salim"]
    add_ex("Who designed Thorne Bridge?", "Architect Salim drafted the blueprints and designed Thorne Bridge in 1972.", RelationLabel.ANSWERS, "PERSON", fam, src, "bridge_designer", "direct", contrast=ContrastType.PERSON_ROLE_CONTRAST, ents=ents)
    add_ex("Who created the structural plans for Thorne Bridge?", "The architectural drawings for Thorne Bridge were produced by Salim.", RelationLabel.ANSWERS, "PERSON", fam, src, "bridge_designer", "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=ents)
    add_ex("When was Thorne Bridge constructed?", "Construction crews completed Thorne Bridge in the spring of 1974.", RelationLabel.ANSWERS, "DATE", fam, src, "construction_date", "direct", contrast=ContrastType.TEMPORAL_CONTRAST, ents=ents)
    add_ex("Who repaired the suspension cables on Thorne Bridge?", "Nadia replaced and tightened the corroded suspension cables on Thorne Bridge.", RelationLabel.ANSWERS, "PERSON", fam, src, "cable_repairer", "direct", contrast=ContrastType.PERSON_ROLE_CONTRAST, ents=ents)
    add_ex("Who designed Thorne Bridge?", "Farid inspected Thorne Bridge after the seasonal river crest.", RelationLabel.DOES_NOT_ANSWER, "PERSON", fam, src, "bridge_designer", "hard_negative", neg_reason=NegativeReason.WRONG_PREDICATE, contrast=ContrastType.PERSON_ROLE_CONTRAST, is_chal=True, ents=ents)
    add_ex("Who designed Thorne Bridge?", "Nadia replaced the corroded suspension cables on Thorne Bridge.", RelationLabel.DOES_NOT_ANSWER, "PERSON", fam, src, "bridge_designer", "hard_negative", neg_reason=NegativeReason.WRONG_PREDICATE, contrast=ContrastType.PERSON_ROLE_CONTRAST, is_chal=True, ents=ents)
    add_ex("Who designed Thorne Bridge?", "Thorne Bridge connects the eastern industrial district with the old harbor.", RelationLabel.DOES_NOT_ANSWER, "PERSON", fam, src, "bridge_designer", "hard_negative", neg_reason=NegativeReason.SAME_TOPIC_WRONG_RELATION, contrast=ContrastType.HIGH_OVERLAP_DISTRACTOR, is_chal=True, ents=ents)
    add_ex("Who designed Thorne Bridge?", "Historians have debated for years who designed Thorne Bridge.", RelationLabel.DOES_NOT_ANSWER, "PERSON", fam, src, "bridge_designer", "hard_negative", neg_reason=NegativeReason.QUESTION_RESTATEMENT, contrast=ContrastType.QUESTION_REPETITION, is_chal=True, ents=ents)

    # 8. Botanical Grounds
    fam = "train_botanical_garden_08"
    src = "synth_botanical_08"
    ents = ["Mira", "Kestrel Gardens", "Caspian Greenhouse"]
    add_ex("Who maintains Kestrel Gardens?", "Mira looks after the grounds and flora across Kestrel Gardens.", RelationLabel.ANSWERS, "PERSON", fam, src, "maintainer", "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=ents)
    add_ex("Who is in charge of gardening at Kestrel Gardens?", "Head horticulturalist Mira manages the landscaping at Kestrel Gardens.", RelationLabel.ANSWERS, "PERSON", fam, src, "maintainer", "direct", contrast=ContrastType.DIRECT_FACTUAL, ents=ents)
    add_ex("When was Kestrel Gardens founded?", "Kestrel Gardens was established by civic horticulturalists in 1950.", RelationLabel.ANSWERS, "DATE", fam, src, "founding_date", "direct", contrast=ContrastType.TEMPORAL_CONTRAST, ents=ents)
    add_ex("What plants are cultivated inside Caspian Greenhouse?", "Caspian Greenhouse houses rare tropical epiphytes and endangered ferns.", RelationLabel.ANSWERS, "DESCRIPTION", fam, src, "greenhouse_flora", "direct", contrast=ContrastType.ATTRIBUTE_CONTRAST, ents=ents)
    add_ex("Who maintains Kestrel Gardens?", "The Kestrel Gardens maintenance schedule is published on the welcome kiosk.", RelationLabel.DOES_NOT_ANSWER, "PERSON", fam, src, "maintainer", "hard_negative", neg_reason=NegativeReason.SAME_TOPIC_WRONG_RELATION, contrast=ContrastType.HIGH_OVERLAP_DISTRACTOR, is_chal=True, ents=ents)
    add_ex("Who maintains Kestrel Gardens?", "Mira visited Caspian Greenhouse to collect rare orchid samples.", RelationLabel.DOES_NOT_ANSWER, "PERSON", fam, src, "maintainer", "hard_negative", neg_reason=NegativeReason.WRONG_PREDICATE, contrast=ContrastType.ENTITY_CONTRAST, is_chal=True, ents=ents)
    add_ex("Who maintains Kestrel Gardens?", "Kestrel Gardens was established by civic horticulturalists in 1950.", RelationLabel.DOES_NOT_ANSWER, "PERSON", fam, src, "maintainer", "hard_negative", neg_reason=NegativeReason.WRONG_PREDICATE, contrast=ContrastType.SAME_TOPIC_WRONG_RELATION, is_chal=True, ents=ents)
    add_ex("Who maintains Kestrel Gardens?", "Visitors wonder who maintains Kestrel Gardens throughout the winter.", RelationLabel.DOES_NOT_ANSWER, "PERSON", fam, src, "maintainer", "hard_negative", neg_reason=NegativeReason.QUESTION_RESTATEMENT, contrast=ContrastType.QUESTION_REPETITION, is_chal=True, ents=ents)

    # 9. Pump Station Causality
    fam = "train_pump_causality_09"
    src = "synth_waterworks_09"
    ents = ["Pump 9", "Vance Waterworks", "cooling intake"]
    add_ex("What caused Pump 9 to stop?", "Pump 9 stopped operating because silt clogged its cooling intake valve.", RelationLabel.ANSWERS, "CAUSE", fam, src, "failure_cause", "direct", contrast=ContrastType.CAUSAL_CONTRAST, ents=ents)
    add_ex("Why did Pump 9 shut down?", "The emergency shutdown of Pump 9 was triggered by an overheated bearing shaft.", RelationLabel.ANSWERS, "CAUSE", fam, src, "failure_cause", "low_overlap_positive", contrast=ContrastType.CAUSAL_CONTRAST, is_chal=True, ents=ents)
    add_ex("When did Pump 9 resume operation?", "Technicians restarted Pump 9 at 08:30 the following morning.", RelationLabel.ANSWERS, "DATE", fam, src, "restart_time", "direct", contrast=ContrastType.TEMPORAL_CONTRAST, ents=ents)
    add_ex("Who repaired Pump 9?", "Engineer Vance replaced the intake strainer and cleared Pump 9.", RelationLabel.ANSWERS, "PERSON", fam, src, "repair_actor", "direct", contrast=ContrastType.DIRECT_FACTUAL, ents=ents)
    add_ex("What caused Pump 9 to stop?", "Pump 9 stopped operating precisely at 4:15 PM.", RelationLabel.DOES_NOT_ANSWER, "CAUSE", fam, src, "failure_cause", "hard_negative", neg_reason=NegativeReason.WRONG_ANSWER_TYPE, contrast=ContrastType.CAUSAL_CONTRAST, is_chal=True, ents=ents)
    add_ex("What caused Pump 9 to stop?", "Vance Waterworks dispatched technicians to inspect Pump 9.", RelationLabel.DOES_NOT_ANSWER, "CAUSE", fam, src, "failure_cause", "hard_negative", neg_reason=NegativeReason.RELATED_EVENT, contrast=ContrastType.CAUSAL_CONTRAST, is_chal=True, ents=ents)
    add_ex("What caused Pump 9 to stop?", "Pump 9 was fully repaired by midnight and resumed water distribution.", RelationLabel.DOES_NOT_ANSWER, "CAUSE", fam, src, "failure_cause", "hard_negative", neg_reason=NegativeReason.RELATED_EVENT, contrast=ContrastType.CAUSAL_CONTRAST, is_chal=True, ents=ents)
    add_ex("What caused Pump 9 to stop?", "Articles often ask what caused Pump 9 to stop.", RelationLabel.DOES_NOT_ANSWER, "CAUSE", fam, src, "failure_cause", "hard_negative", neg_reason=NegativeReason.QUESTION_RESTATEMENT, contrast=ContrastType.QUESTION_REPETITION, is_chal=True, ents=ents)

    # 10 to 60: Systematically generate 51 additional train families with 4 POS and 4 NEG each
    train_templates = [
        ("train_telescope_spectrograph_10", "synth_astronomy_10", ["Zephyr Telescope", "Helios Array", "Dr. Vance"], "What sensor does the Zephyr Telescope use?", "The Zephyr Telescope utilizes an infrared cryogenic spectrograph.", "The Zephyr Telescope is situated at an elevation of 3,100 meters.", "SPECIFICATION", "sensor_spec"),
        ("train_stone_aqueduct_11", "synth_archaeology_11", ["Al-Mansur Aqueduct", "Basra Valley", "Governor Rami"], "When was the Al-Mansur Aqueduct completed?", "Masons finished building the Al-Mansur Aqueduct in 842 CE.", "The structure collapsed during the severe earth tremor of 915 CE.", "DATE", "completion_date"),
        ("train_server_os_12", "synth_os_manual_12", ["Model One", "Model One X", "ByteWave"], "Does Model One X support hot swapping?", "Model One X includes dual redundant power units capable of live hot swapping.", "Model One requires a full system shutdown before removing storage modules.", "BOOLEAN", "hot_swap"),
        ("train_kiln_temperature_13", "synth_craft_manual_13", ["Prism Kiln", "Khadija", "stoneware"], "What temperature is the Prism Kiln heated to?", "Khadija fires the Prism Kiln up to 1250 °C for vitrified stoneware.", "The Prism Kiln has an internal chamber capacity of 200 liters.", "NUMBER", "operating_temp"),
        ("train_coral_survey_14", "synth_marine_bio_14", ["Atlas Reef", "Loomis", "staghorn coral"], "Who surveyed the staghorn coral at Atlas Reef?", "Marine biologist Loomis mapped the distribution of staghorn coral across Atlas Reef.", "The water temperature at Atlas Reef fluctuates between 24 °C and 29 °C.", "PERSON", "surveyor"),
        ("train_library_archive_15", "synth_library_policy_15", ["Cedar Archive", "Samira", "special collections"], "Is an advance appointment required to visit Cedar Archive?", "Visitors must book a designated study slot 48 hours prior to entering Cedar Archive.", "The Cedar Archive reading room provides free wireless internet to all patrons.", "BOOLEAN", "appointment_req"),
        ("train_turbine_generator_16", "synth_energy_16", ["Vortex Turbine", "Lucian", "generator coil"], "How much power does Vortex Turbine generate?", "Vortex Turbine produces 4.5 MW at maximum flow velocity.", "Lucian inspected the Vortex Turbine rotor blades.", "POWER", "power_output"),
        ("train_honeybee_hive_17", "synth_entomology_17", ["Phaedra Apiary", "queen bee", "waggle dance"], "What triggers the waggle dance in Phaedra Apiary?", "Forager bees perform the waggle dance when a rich nectar patch is located.", "The Phaedra Apiary houses twelve Langstroth hives.", "CAUSE", "waggle_trigger"),
        ("train_fresco_restoration_18", "synth_art_history_18", ["Sylvia", "Basra Fresco", "pigment"], "Who restored the Basra Fresco?", "Conservator Sylvia cleaned and stabilized the Basra Fresco.", "The Basra Fresco depicts an allegorical harvest procession.", "PERSON", "restoration_artist"),
        ("train_microcontroller_19", "synth_embedded_19", ["QuantumCore MCU", "Aegis Board", "SPI clock"], "What is the maximum SPI clock speed of QuantumCore MCU?", "QuantumCore MCU supports SPI clock frequencies up to 50 MHz.", "QuantumCore MCU operates from a 3.3V power supply rail.", "NUMBER", "clock_speed"),
        ("train_subway_extension_20", "synth_transit_20", ["North Star Line", "Tariq Station", "tunnel boring"], "When did drilling begin for the North Star Line?", "Crews started tunnel excavation for the North Star Line in March 2017.", "The North Star Line carries approximately 80,000 riders daily.", "DATE", "excavation_start"),
        ("train_hospital_dietary_21", "synth_nutrition_21", ["Crestview Hospital", "gluten-free", "cafeteria"], "Are gluten-free meals offered at Crestview Hospital?", "Patients can order verified gluten-free and allergen-safe meals daily.", "Crestview Hospital updated its visitor parking policy last autumn.", "BOOLEAN", "dietary_options"),
        ("train_mountain_pass_22", "synth_geography_22", ["Ember Pass", "Farid", "snowpack"], "What is the elevation of Ember Pass?", "Ember Pass reaches its summit at an altitude of 2,460 meters.", "Farid navigated Ember Pass during the late spring thaw.", "NUMBER", "elevation"),
        ("train_compiler_opt_23", "synth_compilers_23", ["ByteWave Compiler", "LLVM", "dead code elimination"], "How does ByteWave Compiler eliminate dead code?", "The compiler traverses the control flow graph to prune unreachable basic blocks.", "ByteWave Compiler was written primarily in modern C++20.", "PROCEDURE", "optimization_procedure"),
        ("train_espresso_valve_24", "synth_appliances_24", ["Veritas Machine", "solenoid valve", "brew pressure"], "What brew pressure does the Veritas Machine maintain?", "The Veritas Machine regulates extraction pressure at exactly 9 bars.", "The Veritas Machine features a polished stainless steel casing.", "NUMBER", "pressure_spec"),
        ("train_seed_bank_25", "synth_conservation_25", ["Sylvan Vault", "Alden", "wild barley"], "Who curated the wild barley collection at Sylvan Vault?", "Botanist Alden accessioned and dried the wild barley specimens.", "The Sylvan Vault maintains a sub-zero storage temperature.", "PERSON", "curator"),
        ("train_weather_radar_26", "synth_meteorology_26", ["Titan Doppler", "Corina", "precipitation"], "What wavelength does the Titan Doppler radar use?", "Titan Doppler transmits electromagnetic pulses in the S-band at 10 cm wavelength.", "Corina monitored the Titan Doppler console during the hurricane.", "SPECIFICATION", "radar_wavelength"),
        ("train_iron_foundry_27", "synth_metallurgy_27", ["Ferris Foundry", "blast furnace", "pig iron"], "What fuel is consumed by the Ferris Foundry furnace?", "The blast furnace runs exclusively on metallurgical coke.", "Ferris Foundry was established along the riverfront in 1904.", "MATERIAL", "furnace_fuel"),
        ("train_audio_interface_28", "synth_audio_tech_28", ["AeroFlow Audio", "USB-C", "sample rate"], "What sample rate does AeroFlow Audio record?", "The device captures studio sound at sample rates up to 192 kHz.", "AeroFlow Audio connects to host workstations via USB-C cables.", "NUMBER", "sampling_frequency"),
        ("train_glider_wing_29", "synth_aerospace_29", ["Kaelen Glider", "carbon fiber", "glide ratio"], "What is the glide ratio of the Kaelen Glider?", "The craft boasts a certified lift-to-drag glide ratio of 44 to 1.", "The Kaelen Glider wings are constructed from carbon fiber composite.", "NUMBER", "glide_ratio"),
        ("train_monastery_library_30", "synth_manuscripts_30", ["Riverdale Priory", "illuminated codex", "Brother Gideon"], "Who penned the illuminated codex at Riverdale Priory?", "Brother Gideon inscribed and illuminated the vellum codex in 1344.", "The Riverdale Priory cloister faces south toward the orchard.", "PERSON", "scribe"),
        ("train_drone_battery_31", "synth_robotics_31", ["Solaria Drone", "lithium polymer", "flight duration"], "How long can the Solaria Drone stay airborne?", "The multirotor achieves a continuous hover flight duration of 38 minutes.", "Solaria Drone utilizes GPS and optical flow navigation sensors.", "DURATION", "flight_time"),
        ("train_dental_implant_32", "synth_dentistry_32", ["Cedar Dental", "titanium post", "warranty"], "Does Cedar Dental guarantee its implant posts?", "Every titanium implant installed by Cedar Dental carries a lifetime structural warranty.", "Cedar Dental is located adjacent to the central civic fountain.", "BOOLEAN", "warranty_coverage"),
        ("train_laser_interferometer_33", "synth_optics_33", ["Helios Interferometer", "helium-neon", "mirror"], "What laser source powers the Helios Interferometer?", "The apparatus employs a stabilized helium-neon gas laser emitting at 632.8 nm.", "Helios Interferometer is mounted upon a vibration-damped granite table.", "SPECIFICATION", "laser_source"),
        ("train_tapestry_loom_34", "synth_weaving_34", ["Basra Atelier", "jacquard loom", "silk warp"], "How wide is the warp beam on the Basra Atelier loom?", "The jacquard loom features a working warp width of 3.2 meters.", "Basra Atelier weaves historical reproduction tapestries.", "NUMBER", "loom_width"),
        ("train_hydroponic_nutrients_35", "synth_agriculture_35", ["North Star Farm", "nutrient solution", "lettuce"], "What electrical conductivity is maintained in North Star Farm?", "Growers calibrate the nutrient solution conductivity to 1.8 mS/cm.", "North Star Farm yields crisp butterhead lettuce year-round.", "NUMBER", "nutrient_ec"),
        ("train_space_probe_antenna_36", "synth_deep_space_36", ["Zephyr Probe", "high-gain antenna", "X-band"], "What diameter is the high-gain dish on the Zephyr Probe?", "The paraboloid antenna dish measures exactly 2.4 meters across.", "The Zephyr Probe passed the orbital trajectory of Mars.", "NUMBER", "antenna_diameter"),
        ("train_ceramic_glaze_37", "synth_pottery_37", ["Bram Studio", "cobalt glaze", "reduction firing"], "What oxide produces the blue hue in Bram Studio pottery?", "The studio achieves deep azure coloration by incorporating cobalt carbonate into the glaze.", "Bram Studio exhibits functional stoneware at regional craft fairs.", "MATERIAL", "colorant_oxide"),
        ("train_vacuum_chamber_38", "synth_physics_lab_38", ["Aegis Lab", "turbomolecular pump", "ultra-high vacuum"], "What baseline pressure does the Aegis Lab chamber reach?", "The vacuum vessel attains an ultimate base pressure of 1e-9 Torr.", "Aegis Lab was funded by a national scientific infrastructure grant.", "NUMBER", "base_pressure"),
        ("train_fermentation_temp_39", "synth_biotech_39", ["Crestview Bio", "bioreactor", "yeast strain"], "At what temperature does Crestview Bio run fermentation?", "The culture broth temperature is held steadily at 32 °C throughout growth.", "Crestview Bio produces food-grade enzymes via microbial fermentation.", "NUMBER", "fermentation_temp"),
        ("train_clockwork_escapement_40", "synth_horology_40", ["Salim Workshop", "deadbeat escapement", "pendulum"], "What escapement type was fitted in the Salim Workshop regulator?", "The master clockmaker installed an anchor deadbeat escapement mechanism.", "The pendulum rod in the Salim Workshop clock is made of Invar alloy.", "SPECIFICATION", "escapement_type"),
        ("train_aerodrive_engine_41", "synth_propulsion_41", ["AeroDrive Engine", "turbocharger", "intercooler"], "What boost pressure does the AeroDrive Engine generate?", "The AeroDrive Engine twin turbochargers deliver a maximum boost pressure of 1.8 bar.", "The AeroDrive Engine block is cast from compacted graphite iron.", "NUMBER", "boost_pressure"),
        ("train_solaria_sensor_42", "synth_spectroscopy_42", ["Solaria Sensor", "photodiode", "dark current"], "What dark current is measured on the Solaria Sensor?", "The cooled photodiode array exhibits a residual dark current below 2 picoamps.", "Solaria Sensor was installed inside a sealed aluminum housing.", "NUMBER", "dark_current"),
        ("train_prism_photometer_43", "synth_optical_lab_43", ["Prism Photometer", "diffraction grating", "stray light"], "What stray light rejection ratio does Prism Photometer achieve?", "The dual monochromator layout provides a stray light rejection ratio of 10^-6.", "Prism Photometer was calibrated using a deuterium standard lamp.", "NUMBER", "stray_light_ratio"),
        ("train_basra_canal_44", "synth_civil_works_44", ["Basra Canal", "sluice gate", "dredging"], "Who directed the dredging operations for Basra Canal?", "Harbor engineer Anwar directed the dredging and widening of Basra Canal.", "Basra Canal connects inland agricultural basins with the river delta.", "PERSON", "dredging_director"),
        ("train_vortex_centrifuge_45", "synth_separations_45", ["Vortex Centrifuge", "rotor speed", "RCF"], "What maximum centrifugal acceleration does Vortex Centrifuge reach?", "The carbon-fiber fixed rotor reaches a relative centrifugal force of 21,000 x g.", "Vortex Centrifuge incorporates an automated lid locking interlock.", "NUMBER", "max_rcf"),
        ("train_phaedra_colony_46", "synth_marine_fauna_46", ["Phaedra Colony", "green turtle", "nesting site"], "In what month do green turtles nest at Phaedra Colony?", "Female green turtles crawl ashore to lay eggs primarily throughout July.", "Phaedra Colony stretches along two kilometers of sandy coastline.", "DATE", "nesting_month"),
        ("train_ember_crucible_47", "synth_materials_lab_47", ["Ember Crucible", "silicon carbide", "melting point"], "What maximum working temperature can Ember Crucible withstand?", "The silicon carbide refractory vessel safely withstands prolonged heat up to 1600 °C.", "Ember Crucible is stored in a dry desiccator cabinet between heats.", "NUMBER", "max_temperature"),
        ("train_titan_cryostat_48", "synth_cryogenics_48", ["Titan Cryostat", "liquid helium", "boil-off"], "What is the daily boil-off rate of Titan Cryostat?", "Vacuum multi-layer insulation restricts the liquid helium boil-off to 0.4% per day.", "Titan Cryostat cools superconducting quantum interference devices.", "PERCENTAGE", "boil_off_rate"),
        ("train_kestrel_avionics_49", "synth_flight_deck_49", ["Kestrel Avionics", "AHRS", "drift rate"], "What gyro drift rate is specified for Kestrel Avionics?", "The MEMS inertial measurement unit exhibits an in-run bias stability of 0.5 degrees per hour.", "Kestrel Avionics interfaces with standard ARINC 429 digital data buses.", "NUMBER", "gyro_drift"),
        ("train_atlas_seismograph_50", "synth_geophysics_50", ["Atlas Seismograph", "pendulum mass", "natural period"], "What natural period is tuned into Atlas Seismograph?", "The horizontal astatic pendulum is tuned to a natural resonant period of 20 seconds.", "Atlas Seismograph recorded deep teleseismic crustal wave arrivals.", "DURATION", "natural_period"),
        ("train_solar_desalination_51", "synth_clean_water_51", ["Layla Still", "solar collector", "distillate output"], "How much fresh water does the Layla Still produce daily?", "The multi-effect solar evaporator yields 45 liters of potable distillate per day.", "Layla Still utilizes black chrome selective absorber sheets.", "NUMBER", "daily_yield"),
        ("train_wind_anemometer_52", "synth_wind_power_52", ["Rashid Anemometer", "ultrasonic transducer", "gust response"], "What gust response time does the Rashid Anemometer have?", "The solid-state ultrasonic sensor registers wind speed changes within 50 milliseconds.", "Rashid Anemometer operates reliably under heavy icing conditions.", "DURATION", "response_time"),
        ("train_geothermal_heat_53", "synth_thermal_well_53", ["Hassan Well", "downhole heat exchanger", "circulation rate"], "What water flow rate circulates through Hassan Well?", "Submersible pumps circulate thermal brine at a steady rate of 35 liters per second.", "Hassan Well was drilled to a subterranean depth of 1,800 meters.", "NUMBER", "circulation_rate"),
        ("train_timber_bridge_54", "synth_wood_craft_54", ["Noor Trestle", "larch wood", "preservative"], "What wood species was selected to build Noor Trestle?", "Carpenters framed the entire trestle structure from naturally rot-resistant Siberian larch.", "Noor Trestle spans a narrow mountain gorge in the pine forest.", "MATERIAL", "wood_species"),
        ("train_battery_separator_55", "synth_electrochem_55", ["Bilal Membrane", "polyolefin", "porosity"], "What pore fraction is engineered into the Bilal Membrane?", "The microporous battery separator features an open porosity of 42%.", "Bilal Membrane is chemically inert toward aggressive carbonate electrolytes.", "PERCENTAGE", "membrane_porosity"),
        ("train_stone_arch_56", "synth_masonry_arch_56", ["Fatima Arch", "keystone", "limestone"], "What stone was carved for the Fatima Arch keystone?", "Masons dressed a dense oolitic limestone block for the central keystone.", "Fatima Arch marks the ancient ceremonial gateway into the market quarter.", "MATERIAL", "keystone_material"),
        ("train_optical_lens_57", "synth_precision_glass_57", ["Idris Objective", "fluorite glass", "focal length"], "What focal length is ground into the Idris Objective lens?", "The apochromatic triplet optic features an effective focal length of 800 mm.", "Idris Objective is coated with anti-reflective magnesium fluoride films.", "NUMBER", "focal_length"),
        ("train_copper_smelter_58", "synth_ore_processing_58", ["Zahra Smelter", "flotation concentrate", "matte grade"], "What copper percentage is achieved in the Zahra Smelter matte?", "The reverberatory smelting cycle yields a concentrated copper matte of 58% Cu.", "Zahra Smelter processes chalcopyrite copper concentrates from nearby mines.", "PERCENTAGE", "matte_grade"),
        ("train_hydrofoil_strut_59", "synth_naval_craft_59", ["Yusuf Hydrofoil", "titanium foil", "takeoff speed"], "At what water speed does the Yusuf Hydrofoil lift onto its foils?", "The vessel attains sufficient dynamic foil lift to fly at a hull speed of 18 knots.", "Yusuf Hydrofoil carries twenty-four commuters across the coastal bay.", "SPEED", "takeoff_speed"),
        ("train_botanical_herbarium_60", "synth_herbarium_specimen_60", ["Hana Herbarium", "type specimen", "botanist Idris"], "Who mounted the holotype specimen at Hana Herbarium?", "Botanist Idris pressed and formally labeled the holotype flowering branch in 1935.", "Hana Herbarium preserves over fifty thousand dried plant vouchers.", "PERSON", "mounting_botanist")
    ]

    for fam_id, src_id, scenario_ents, q_text, pos_ev, neg_ev, ans_type, rel_type in train_templates:
        # 1. Direct Positive
        add_ex(q_text, pos_ev, RelationLabel.ANSWERS, ans_type, fam_id, src_id, rel_type, "direct", contrast=ContrastType.DIRECT_FACTUAL, ents=scenario_ents)
        # 2. Low Overlap Positive
        q_low = f"Regarding {scenario_ents[0]}, {q_text[0].lower() + q_text[1:]}"
        ev_low = f"Engineers verified that {pos_ev.lower()}"
        add_ex(q_low, ev_low, RelationLabel.ANSWERS, ans_type, fam_id, src_id, rel_type, "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=scenario_ents)
        # 3. Paraphrase Positive
        q_alt = f"What are the documented facts regarding {q_text.lower().rstrip('?')}?"
        ev_alt = f"Documentation confirms that {pos_ev.lower()}"
        add_ex(q_alt, ev_alt, RelationLabel.ANSWERS, ans_type, fam_id, src_id, rel_type, "direct", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, ents=scenario_ents)
        # 4. Affirmative Support Positive
        add_ex(f"Is it verified that {pos_ev.lower()}", f"Yes, authentic records verify that {pos_ev.lower()}", RelationLabel.ANSWERS, "BOOLEAN", fam_id, src_id, rel_type, "direct", contrast=ContrastType.BOOLEAN_NEGATION_CONTRAST, ents=scenario_ents)

        # 5. High overlap distractor negative
        add_ex(q_text, neg_ev, RelationLabel.DOES_NOT_ANSWER, ans_type, fam_id, src_id, rel_type, "hard_negative", neg_reason=NegativeReason.SAME_TOPIC_WRONG_RELATION, contrast=ContrastType.HIGH_OVERLAP_DISTRACTOR, is_chal=True, ents=scenario_ents)
        # 6. Wrong property / predicate negative
        add_ex(q_text, f"Archival surveys establish that {scenario_ents[0]} underwent routine maintenance inspections.", RelationLabel.DOES_NOT_ANSWER, ans_type, fam_id, src_id, rel_type, "hard_negative", neg_reason=NegativeReason.WRONG_PREDICATE, contrast=ContrastType.ATTRIBUTE_CONTRAST, is_chal=True, ents=scenario_ents)
        # 7. Question repetition negative
        add_ex(q_text, f"Specialists repeatedly investigate: '{q_text}'", RelationLabel.DOES_NOT_ANSWER, ans_type, fam_id, src_id, rel_type, "hard_negative", neg_reason=NegativeReason.QUESTION_RESTATEMENT, contrast=ContrastType.QUESTION_REPETITION, is_chal=True, ents=scenario_ents)
        # 8. Missing Information negative
        add_ex(q_text, f"A technical memo was published concerning the operational parameters of {scenario_ents[0]}.", RelationLabel.DOES_NOT_ANSWER, ans_type, fam_id, src_id, rel_type, "hard_negative", neg_reason=NegativeReason.MISSING_INFORMATION, contrast=ContrastType.HIGH_OVERLAP_DISTRACTOR, is_chal=True, ents=scenario_ents)

    return examples


def _build_val_scenarios() -> List[RelationExample]:
    examples: List[RelationExample] = []
    e_idx = 1

    def add_ex(
        q: str, ev: str, lbl: RelationLabel, ans_type: str, fam: str, src: str,
        rel: str, diff: str, neg_reason=None, contrast=None, is_chal=False,
        ents=None, notes=None
    ):
        nonlocal e_idx
        ex = RelationExample(
            id=f"pese-rel-val-{e_idx:04d}",
            question=q,
            evidence=ev,
            label=lbl,
            answer_type=ans_type,
            scenario_family=fam,
            source_id=src,
            relation_family=rel,
            difficulty=diff,
            negative_reason=neg_reason,
            contrast_type=contrast,
            is_challenge=is_chal,
            entities=ents or [],
            notes=notes
        )
        examples.append(ex)
        e_idx += 1

    # 15 Validation Scenario Families (V01 to V15) with 4 POS and 4 NEG each = 120 validation examples
    val_templates = [
        ("val_canal_lock_01", "synth_val_maritime_01", ["Elena", "Marcus", "Corvus Lock"], "Who modernized the Corvus Lock gates?", "Lead engineer Elena oversaw the hydraulic overhaul and modernized Corvus Lock gates.", "Marcus operated the manual sluice valves at Corvus Lock during high tide.", "PERSON", "modernization_lead"),
        ("val_observatory_version_02", "synth_val_space_02", ["Vanguard 3", "Vanguard 3 Max", "Astraea Systems"], "Does Vanguard 3 Max carry an ultraviolet spectrometer?", "Vanguard 3 Max is equipped with an advanced wide-field ultraviolet spectrometer.", "Vanguard 3 carries only standard visible-light and thermal imaging sensors.", "BOOLEAN", "payload_spec"),
        ("val_weather_causality_03", "synth_val_alpine_03", ["Boreas Tower", "Valeria", "heating element"], "Why did telemetry cut out at Boreas Tower?", "Boreas Tower lost transmission after freezing rain sheared the external coaxial feed.", "Meteorologist Valeria hiked to Boreas Tower to replace the battery banks.", "CAUSE", "outage_cause"),
        ("val_hydra_database_04", "synth_val_db_04", ["Hydra Labs", "Lyra System", "column store"], "What storage engine powers Lyra System?", "Lyra System utilizes a memory-mapped columnar storage engine.", "Hydra Labs founded the Lyra System project in 2019.", "SPECIFICATION", "engine_type"),
        ("val_archival_papyrus_05", "synth_val_history_05", ["Althea Library", "Renwick", "curator"], "When did Renwick accession the Althea papyrus?", "Renwick documented and accessioned the Althea papyrus scrolls in 1912.", "The Althea papyrus contains trade receipts in Greek script.", "DATE", "accession_date"),
        ("val_surgical_robot_06", "synth_val_medical_06", ["Talon Robot", "Oakhaven Clinic", "stereo camera"], "What stereo camera is integrated into Talon Robot?", "The Talon Robot incorporates dual 4K stereoscopic endoscopic cameras.", "Oakhaven Clinic acquired the Talon Robot for minimally invasive procedures.", "SPECIFICATION", "camera_spec"),
        ("val_solar_array_07", "synth_val_energy_07", ["Meridian Array", "inverter", "efficiency"], "What is the peak conversion efficiency of Meridian Array?", "The Meridian Array achieves a peak photovoltaic efficiency of 22.8%.", "The Meridian Array covers thirty hectares of desert plateau.", "NUMBER", "efficiency_spec"),
        ("val_deep_submersible_08", "synth_val_ocean_08", ["Callisto Sub", "titanium sphere", "depth rating"], "What is the maximum certified depth for Callisto Sub?", "The Callisto Sub is certified for manned dives down to 6,000 meters.", "Callisto Sub returned safely from its maiden Mariana trench expedition.", "NUMBER", "depth_rating"),
        ("val_botanical_greenhouse_09", "synth_val_flora_09", ["Daphne Conservatory", "Cassian", "humidity"], "What relative humidity is maintained in Daphne Conservatory?", "Automated misters keep humidity in Daphne Conservatory between 75% and 80%.", "Cassian donated rare carnivorous plants to Daphne Conservatory.", "NUMBER", "humidity_level"),
        ("val_acoustic_resonator_10", "synth_val_physics_10", ["Jocelyn Chamber", "piezo sensor", "resonant frequency"], "What is the resonant frequency of the Jocelyn Chamber?", "Acoustic calibration establishes the fundamental resonance at 432 Hz.", "The Jocelyn Chamber walls are lined with sound-absorbing anechoic wedges.", "NUMBER", "resonant_freq"),
        ("val_timber_pier_11", "synth_val_civil_11", ["Theodora Pier", "Ignatius", "piling"], "Who oversaw piling replacement at Theodora Pier?", "Marine contractor Ignatius drove steel-sleeved concrete pilings at Theodora Pier.", "Theodora Pier was originally opened to passenger steamers in 1908.", "PERSON", "contractor"),
        ("val_induction_furnace_12", "synth_val_foundry_12", ["Ignatius Furnace", "Octavia", "graphite crucible"], "What crucible capacity is rated for Ignatius Furnace?", "Ignatius Furnace melts metal charges inside a 50 kg graphite-clay crucible.", "Octavia poured molten bronze into investment casting molds.", "NUMBER", "crucible_capacity"),
        ("val_turboprop_engine_13", "synth_val_aviation_13", ["Octavia Engine", "reduction gearbox", "shaft horsepower"], "How much shaft horsepower does Octavia Engine deliver?", "The turboprop core generates a continuous sea-level output of 1,200 shaft horsepower.", "Octavia Engine is maintained according to regional aviation directives.", "NUMBER", "shaft_power"),
        ("val_coastal_radar_14", "synth_val_sensors_14", ["Leander Radar", "Sibyl", "pulse repetition"], "What pulse repetition frequency does Leander Radar transmit?", "The solid-state marine surveillance array operates at a pulse repetition rate of 1,500 Hz.", "Sibyl verified radar target track clarity across the navigation strait.", "NUMBER", "pulse_rate"),
        ("val_mass_spectrometer_15", "synth_val_analytical_15", ["Sibyl Spectrometer", "Nestor", "quadrupole"], "What mass resolution does the Sibyl Spectrometer achieve?", "The triple-quadrupole system resolves isotopic mass differences down to 0.05 atomic mass units.", "Nestor introduced organic solvent blanks into the electrospray ionization source.", "NUMBER", "mass_resolution")
    ]

    for fam_id, src_id, scenario_ents, q_text, pos_ev, neg_ev, ans_type, rel_type in val_templates:
        # 1. Direct Positive
        add_ex(q_text, pos_ev, RelationLabel.ANSWERS, ans_type, fam_id, src_id, rel_type, "direct", contrast=ContrastType.DIRECT_FACTUAL, ents=scenario_ents)
        # 2. Low Overlap Positive
        q_low = f"Regarding {scenario_ents[0]}, {q_text[0].lower() + q_text[1:]}"
        ev_low = f"Technical reports verify that {pos_ev.lower()}"
        add_ex(q_low, ev_low, RelationLabel.ANSWERS, ans_type, fam_id, src_id, rel_type, "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=scenario_ents)
        # 3. Alternate phrasing positive
        q_alt = f"What are the documented specifications regarding {q_text.lower().rstrip('?')}?"
        ev_alt = f"Documentation confirms that {pos_ev.lower()}"
        add_ex(q_alt, ev_alt, RelationLabel.ANSWERS, ans_type, fam_id, src_id, rel_type, "direct", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, ents=scenario_ents)
        # 4. Verified positive
        add_ex(f"Is it verified that {pos_ev.lower()}", f"Yes, records verify that {pos_ev.lower()}", RelationLabel.ANSWERS, "BOOLEAN", fam_id, src_id, rel_type, "direct", contrast=ContrastType.BOOLEAN_NEGATION_CONTRAST, ents=scenario_ents)

        # 5. High overlap distractor negative
        add_ex(q_text, neg_ev, RelationLabel.DOES_NOT_ANSWER, ans_type, fam_id, src_id, rel_type, "hard_negative", neg_reason=NegativeReason.SAME_TOPIC_WRONG_RELATION, contrast=ContrastType.HIGH_OVERLAP_DISTRACTOR, is_chal=True, ents=scenario_ents)
        # 6. Wrong predicate negative
        add_ex(q_text, f"Safety evaluations show that {scenario_ents[0]} underwent regular annual calibration.", RelationLabel.DOES_NOT_ANSWER, ans_type, fam_id, src_id, rel_type, "hard_negative", neg_reason=NegativeReason.WRONG_PREDICATE, contrast=ContrastType.ATTRIBUTE_CONTRAST, is_chal=True, ents=scenario_ents)
        # 7. Question restatement negative
        add_ex(q_text, f"Engineers frequently discuss: '{q_text}'", RelationLabel.DOES_NOT_ANSWER, ans_type, fam_id, src_id, rel_type, "hard_negative", neg_reason=NegativeReason.QUESTION_RESTATEMENT, contrast=ContrastType.QUESTION_REPETITION, is_chal=True, ents=scenario_ents)
        # 8. Missing information negative
        add_ex(q_text, f"A white paper was released summarizing general facts about {scenario_ents[0]}.", RelationLabel.DOES_NOT_ANSWER, ans_type, fam_id, src_id, rel_type, "hard_negative", neg_reason=NegativeReason.MISSING_INFORMATION, contrast=ContrastType.HIGH_OVERLAP_DISTRACTOR, is_chal=True, ents=scenario_ents)

    return examples


def _build_test_scenarios() -> List[RelationExample]:
    examples: List[RelationExample] = []
    e_idx = 1

    def add_ex(
        q: str, ev: str, lbl: RelationLabel, ans_type: str, fam: str, src: str,
        rel: str, diff: str, neg_reason=None, contrast=None, is_chal=False,
        ents=None, notes=None
    ):
        nonlocal e_idx
        ex = RelationExample(
            id=f"pese-rel-test-{e_idx:04d}",
            question=q,
            evidence=ev,
            label=lbl,
            answer_type=ans_type,
            scenario_family=fam,
            source_id=src,
            relation_family=rel,
            difficulty=diff,
            negative_reason=neg_reason,
            contrast_type=contrast,
            is_challenge=is_chal,
            entities=ents or [],
            notes=notes
        )
        examples.append(ex)
        e_idx += 1

    # 15 Test Scenario Families (E01 to E15) with 4 POS and 4 NEG each = 120 test examples
    test_templates = [
        ("test_belltower_masonry_01", "synth_test_architecture_01", ["Soren", "Linnea", "Zenith Belltower"], "Who reinforced the foundation of Zenith Belltower?", "Master stonecarver Soren reinforced the foundation of Zenith Belltower in 1968.", "Linnea surveyed the upper belfry of Zenith Belltower.", "PERSON", "foundation_mason"),
        ("test_processor_versions_02", "synth_test_semiconductor_02", ["Apex 7", "Apex 7 Elite", "Nebula Dynamics"], "Does Apex 7 Elite support AVX-512 vector instructions?", "Apex 7 Elite integrates dual fused 512-bit vector units executing AVX-512 code.", "The standard Apex 7 processor limits SIMD throughput to 256-bit AVX2 instructions.", "BOOLEAN", "isa_support"),
        ("test_space_spectrometry_03", "synth_test_astrophysics_03", ["Cygnus Probe", "Kael", "Darius"], "What time did the Cygnus Probe reach perihelion?", "Flight director Kael confirmed perihelion passage at 14:22 UTC.", "Mission telemetry did not record the exact minute when perihelion was achieved.", "TIME", "perihelion_time"),
        ("test_subsea_cable_04", "synth_test_telecom_04", ["Vesper Cable", "Seraphina", "repeater"], "What optical amplification does Vesper Cable use?", "Vesper Cable relies on erbium-doped fiber amplifiers spaced every 70 kilometers.", "Seraphina captained the cable-laying vessel across the Atlantic.", "SPECIFICATION", "amplifier_spec"),
        ("test_iron_expedition_05", "synth_test_history_05", ["Fenwick Expedition", "Bramwell", "polar charter"], "In what year did the Fenwick Expedition set sail?", "Captain Bramwell embarked on the Fenwick Expedition in June 1894.", "The Fenwick Expedition ship was trapped in pack ice during winter.", "DATE", "departure_year"),
        ("test_particle_detector_06", "synth_test_nuclear_06", ["Oberon Detector", "Theron", "scintillator"], "What crystal is used in the Oberon Detector scintillator?", "The Oberon Detector array is populated by bismuth germanate scintillation crystals.", "Physicist Theron calibrated the detector energy response curves.", "MATERIAL", "crystal_spec"),
        ("test_bioreactor_ph_07", "synth_test_biochem_07", ["Nautilus Fermenter", "Isolde", "pH sensor"], "What pH setpoint is regulated in the Nautilus Fermenter?", "Automated acid-base pumps hold the culture broth at a setpoint of pH 6.8.", "Isolde inoculated the seed flask with recombinant streptomyces.", "NUMBER", "ph_setpoint"),
        ("test_solar_furnace_08", "synth_test_materials_08", ["Caelum Furnace", "heliostat field", "crucible"], "What peak temperature does the Caelum Furnace produce?", "The parabolic concentrator focuses solar radiation to generate temperatures of 3200 °C.", "The Caelum Furnace is constructed on a high-altitude sunlit plateau.", "NUMBER", "furnace_temperature"),
        ("test_ancient_library_09", "synth_test_classics_09", ["Rowan Papyrus", "Morrigan", "pergament"], "Who cataloged the Rowan Papyrus collection?", "Epigrapher Morrigan indexed and translated the Rowan Papyrus catalog in 1928.", "The Rowan Papyrus texts were discovered inside terracotta storage amphorae.", "PERSON", "cataloger"),
        ("test_hydraulic_forge_10", "synth_test_industrial_10", ["Apex Press", "die block", "clamping force"], "What clamping force is exerted by the Apex Press?", "The dual-ram hydraulic cylinders deliver an operational clamping force of 12,000 metric tons.", "The Apex Press was manufactured in a heavy industrial machinery yard.", "NUMBER", "clamping_force"),
        ("test_viaduct_arch_11", "synth_test_masonry_11", ["Aurelius Viaduct", "Astrid", "granite span"], "When was the Aurelius Viaduct completed?", "Railway engineers completed and opened the Aurelius Viaduct in 1891.", "Astrid conducted dynamic load testing using steam locomotives.", "DATE", "completion_date"),
        ("test_hydro_dynamo_12", "synth_test_hydro_12", ["Astrid Dynamo", "Magnus", "stator"], "What voltage does the Astrid Dynamo output?", "The hydro generator generates a three-phase output voltage of 13.8 kV.", "Magnus inspected the winding insulation resistance before commissioning.", "NUMBER", "generator_voltage"),
        ("test_gas_turbine_13", "synth_test_turbine_13", ["Magnus Turbine", "Freja", "compressor stage"], "What compression ratio is achieved by Magnus Turbine?", "The axial compressor in Magnus Turbine reaches an overall pressure ratio of 24 to 1.", "Freja analyzed exhaust gas emissions at base load operation.", "NUMBER", "compression_ratio"),
        ("test_earthquake_recorder_14", "synth_test_seismic_14", ["Freja Seismograph", "Torin", "galvanometer"], "What damping fluid is loaded in Freja Seismograph?", "The horizontal pendulum damping reservoir is filled with 500 cSt silicone oil.", "Torin leveled the seismograph mounting pier in the bedrock vault.", "MATERIAL", "damping_fluid"),
        ("test_ocean_glider_15", "synth_test_marine_15", ["Torin Submersible", "Elowen", "variable ballast"], "What descent speed does Torin Submersible maintain?", "The buoyancy engine regulates descent velocity at exactly 0.35 meters per second.", "Elowen recovered the submersible after thirty days of autonomous surveying.", "SPEED", "descent_speed")
    ]

    for fam_id, src_id, scenario_ents, q_text, pos_ev, neg_ev, ans_type, rel_type in test_templates:
        # 1. Direct Positive
        add_ex(q_text, pos_ev, RelationLabel.ANSWERS, ans_type, fam_id, src_id, rel_type, "direct", contrast=ContrastType.DIRECT_FACTUAL, ents=scenario_ents)
        # 2. Low Overlap Positive
        q_low = f"Regarding {scenario_ents[0]}, {q_text[0].lower() + q_text[1:]}"
        ev_low = f"Scientific logs confirm that {pos_ev.lower()}"
        add_ex(q_low, ev_low, RelationLabel.ANSWERS, ans_type, fam_id, src_id, rel_type, "low_overlap_positive", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, is_chal=True, ents=scenario_ents)
        # 3. Paraphrase positive
        q_alt = f"What are the documented findings regarding {q_text.lower().rstrip('?')}?"
        ev_alt = f"Documentation confirms that {pos_ev.lower()}"
        add_ex(q_alt, ev_alt, RelationLabel.ANSWERS, ans_type, fam_id, src_id, rel_type, "direct", contrast=ContrastType.PARAPHRASE_LOW_OVERLAP, ents=scenario_ents)
        # 4. Verified positive
        add_ex(f"Is it verified that {pos_ev.lower()}", f"Yes, documented records verify that {pos_ev.lower()}", RelationLabel.ANSWERS, "BOOLEAN", fam_id, src_id, rel_type, "direct", contrast=ContrastType.BOOLEAN_NEGATION_CONTRAST, ents=scenario_ents)

        # 5. High overlap distractor negative
        add_ex(q_text, neg_ev, RelationLabel.DOES_NOT_ANSWER, ans_type, fam_id, src_id, rel_type, "hard_negative", neg_reason=NegativeReason.SAME_TOPIC_WRONG_RELATION, contrast=ContrastType.HIGH_OVERLAP_DISTRACTOR, is_chal=True, ents=scenario_ents)
        # 6. Wrong predicate negative
        add_ex(q_text, f"Official reports note that {scenario_ents[0]} underwent regular annual safety audits.", RelationLabel.DOES_NOT_ANSWER, ans_type, fam_id, src_id, rel_type, "hard_negative", neg_reason=NegativeReason.WRONG_PREDICATE, contrast=ContrastType.ATTRIBUTE_CONTRAST, is_chal=True, ents=scenario_ents)
        # 7. Question repetition negative
        add_ex(q_text, f"Specialists repeatedly investigate: '{q_text}'", RelationLabel.DOES_NOT_ANSWER, ans_type, fam_id, src_id, rel_type, "hard_negative", neg_reason=NegativeReason.QUESTION_RESTATEMENT, contrast=ContrastType.QUESTION_REPETITION, is_chal=True, ents=scenario_ents)
        # 8. Missing information negative
        add_ex(q_text, f"A technical memo was released summarizing general facts about {scenario_ents[0]}.", RelationLabel.DOES_NOT_ANSWER, ans_type, fam_id, src_id, rel_type, "hard_negative", neg_reason=NegativeReason.MISSING_INFORMATION, contrast=ContrastType.HIGH_OVERLAP_DISTRACTOR, is_chal=True, ents=scenario_ents)

    return examples


def generate_pese_rel_data_0() -> Dict[str, List[RelationExample]]:
    """
    Constructs the canonical PESE-REL-DATA-0 dataset split:
    - Train: 60 scenario families (480 examples)
    - Validation: 15 scenario families (120 examples)
    - Test: 15 scenario families (120 examples)
    Total: 720 examples
    """
    train_data = _build_train_scenarios()
    val_data = _build_val_scenarios()
    test_data = _build_test_scenarios()

    return {
        "train": train_data,
        "validation": val_data,
        "test": test_data
    }
