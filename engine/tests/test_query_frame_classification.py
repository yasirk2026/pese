"""
Unit tests for PESE QueryFrame Interrogative / Answer-Type Classification (RC3-B).

Verifies that questions are classified by the requested answer slot rather than
the presence of an interrogative word anywhere in the sentence (e.g. subordinate clauses).
"""

import pytest
from engine.passages.answer_pipeline import QueryFrame
from engine.query_analysis.intent import classify_query_intent, QueryIntent
from engine.nlp.tokenizer import tokenize


# Balanced development classification dataset (102 questions)
CLASSIFICATION_BENCHMARK = [
    # Subordinate 'when' / 'after' / 'before' traps
    ("What should I do first when returning the equipment?", "PROCEDURE"),
    ("What should I check before returning the equipment?", "PROCEDURE"),
    ("Who should I contact when my payment fails?", "PERSON"),
    ("Who should I call when the server crashes?", "PERSON"),
    ("Where should I leave the equipment when I am done?", "LOCATION"),
    ("Where should I go when the office closes?", "LOCATION"),
    ("What happens when I return the equipment?", "DESCRIPTION"),
    ("What happens when the server crashes?", "DESCRIPTION"),
    ("How do I return the equipment when the office is closed?", "PROCEDURE"),
    ("Does the clinic accept installments when paying for surgery?", "BOOLEAN"),
    ("Why did the server crash when handling the request?", "CAUSE"),
    ("Who should I contact after my payment fails?", "PERSON"),
    ("Where should I go before the store opens?", "LOCATION"),
    ("Why did the alarm sound during the night?", "CAUSE"),
    ("How long did the blackout last when the storm hit?", "QUANTITY"),
    ("How much was spent on repairs after the accident?", "PRICE"),
    ("Can I split the fee if I pay online?", "BOOLEAN"),
    ("What should I do once the download finishes?", "PROCEDURE"),
    ("What is the second step when installing the drive?", "PROCEDURE"),

    # Subordinate prefix inversion traps
    ("When returning the equipment, what should I do first?", "PROCEDURE"),
    ("When the payment fails, who should I contact?", "PERSON"),
    ("When the office closes, where should I leave the key?", "LOCATION"),
    ("After the alarm sounds, who should I call?", "PERSON"),
    ("Before cleaning the bicycle, what should I check?", "PROCEDURE"),
    ("When returning the bicycle, where do I park it?", "LOCATION"),
    ("Before restarting the server, who must be notified?", "PERSON"),
    ("If the office is closed, how do I submit the form?", "PROCEDURE"),

    # Genuine temporal (DATE / YEAR / CENTURY)
    ("When did Japan enter World War II?", "DATE"),
    ("When was PESE created?", "DATE"),
    ("When does the shop open?", "DATE"),
    ("When did Nadia repair the clock?", "DATE"),
    ("What year was the console released?", "YEAR"),
    ("In what year was the treaty signed?", "YEAR"),
    ("What century did the Renaissance begin?", "CENTURY"),
    ("In which century was the city founded?", "CENTURY"),
    ("What date was the treaty signed?", "DATE"),
    ("What weekday does the market open?", "DATE"),
    ("What time did Teva begin the canoe inspection?", "DATE"),
    ("What time does the store close?", "DATE"),

    # PERSON & ORGANIZATION
    ("Who repaired the station clock?", "PERSON"),
    ("Who founded the company?", "PERSON"),
    ("Who was the chief engineer?", "PERSON"),
    ("Who owns the clinic?", "PERSON"),
    ("Which company developed the console?", "ORGANIZATION"),
    ("Which organization issued the guidelines?", "ORGANIZATION"),
    ("Which association oversees the competition?", "ORGANIZATION"),
    ("Which founder signed the deed?", "PERSON"),
    ("Which studio developed the engine?", "ORGANIZATION"),

    # LOCATION
    ("Where was the bicycle stored?", "LOCATION"),
    ("Where is the clinic located?", "LOCATION"),
    ("Where was the treaty signed?", "LOCATION"),
    ("In which city was the company founded?", "LOCATION"),

    # HOW / NUMBER / QUANTITY / PRICE / PROCEDURE
    ("How do I reset the router?", "PROCEDURE"),
    ("How should I clean the bicycle chain?", "PROCEDURE"),
    ("How to replace the brake pads?", "PROCEDURE"),
    ("How many wheels does it have?", "NUMBER"),
    ("How many chapters are in the book?", "NUMBER"),
    ("How much does it cost?", "PRICE"),
    ("How much is the annual subscription?", "PRICE"),
    ("What is the price of the bicycle?", "PRICE"),
    ("What does the console cost?", "PRICE"),
    ("How much does it weigh?", "QUANTITY"),
    ("How long does the warranty last?", "QUANTITY"),
    ("How heavy is the frame?", "QUANTITY"),

    # BOOLEAN
    ("Does the clinic accept installments?", "BOOLEAN"),
    ("Can I split the fee?", "BOOLEAN"),
    ("Is the office open today?", "BOOLEAN"),
    ("Has the package arrived?", "BOOLEAN"),
    ("Did Nadia repair the clock?", "BOOLEAN"),
    ("Was the treaty ratified in 1945?", "BOOLEAN"),

    # CAUSE
    ("Why did the server stop?", "CAUSE"),
    ("What caused the server outage?", "CAUSE"),
    ("Why was the event cancelled?", "CAUSE"),
    ("What is the cause of the failure?", "CAUSE"),
    ("What is the reason for the delay?", "CAUSE"),

    # DEFINITION
    ("What is PESE?", "DEFINITION"),
    ("What is a transformer?", "DEFINITION"),
    ("What does PESE mean?", "DEFINITION"),
    ("What does CPU mean?", "DEFINITION"),
    ("What is the definition of BM25?", "DEFINITION"),
    ("Define semantic retrieval.", "DEFINITION"),
    ("Define inverted index.", "DEFINITION"),

    # ATTRIBUTE_VALUE
    ("What color is the bicycle?", "ATTRIBUTE_VALUE"),
    ("What brakes does my bicycle use?", "ATTRIBUTE_VALUE"),
    ("What material is the frame made from?", "ATTRIBUTE_VALUE"),
    ("Which processor does the console use?", "ATTRIBUTE_VALUE"),
    ("What is the capital of Japan?", "ATTRIBUTE_VALUE"),
    ("What temperature is the kiln heated to?", "ATTRIBUTE_VALUE"),
    ("What is the color of the frame?", "ATTRIBUTE_VALUE"),
    ("What are the specifications of the engine?", "ATTRIBUTE_VALUE"),

    # Adversarial Pairs
    ("When did Nadia repair the clock?", "DATE"),
    ("Who repaired the clock when it stopped?", "PERSON"),
    ("Where was the bicycle stored?", "LOCATION"),
    ("When was the bicycle stored there?", "DATE"),
    ("What caused the outage?", "CAUSE"),
    ("What happened during the outage?", "DESCRIPTION"),
    ("How do I reset it?", "PROCEDURE"),
    ("How many times should I reset it?", "NUMBER"),
    ("What year was the building completed?", "YEAR"),
    ("What was completed in that year?", "DESCRIPTION"),
    ("Who should I call after the alarm sounds?", "PERSON"),
    ("When does the alarm sound?", "DATE"),
]


@pytest.mark.parametrize("query, expected_type", CLASSIFICATION_BENCHMARK)
def test_query_frame_classification_benchmark(query, expected_type):
    frame = QueryFrame.parse(query)
    assert frame.expected_answer_type == expected_type, (
        f"Query: '{query}' -> Expected '{expected_type}', got '{frame.expected_answer_type}' "
        f"(rule: {frame.matched_rule}, reason: {frame.classification_reason})"
    )


def test_rc2_specific_failure_cases():
    # Retest exact RC2 reported failure cases
    frame1 = QueryFrame.parse("What should I do first when returning the equipment?")
    assert frame1.expected_answer_type == "PROCEDURE"
    assert "when" in frame1.classification_reason.lower()
    assert frame1.matched_rule == "PROCEDURE_WHAT_SHOULD_DO"

    frame2 = QueryFrame.parse("What time did Teva begin the canoe inspection?")
    assert frame2.expected_answer_type == "DATE"
    assert frame2.matched_rule == "DATE_WHAT_TIME"


def test_debug_visibility_fields_exposed():
    frame = QueryFrame.parse("What should I do first when returning the equipment?")
    assert frame.main_interrogative != ""
    assert frame.classification_reason != ""
    assert frame.matched_rule != ""


def test_intent_classification_subordinate_immunity():
    # Ensure query_analysis/intent.py also respects main clause over subordinate when
    toks1 = tokenize("What should I do first when returning the equipment?")
    intent1, _ = classify_query_intent(toks1, "What should I do first when returning the equipment?")
    assert intent1 == QueryIntent.HOW

    toks2 = tokenize("Where should I leave the equipment when I am done?")
    intent2, _ = classify_query_intent(toks2, "Where should I leave the equipment when I am done?")
    assert intent2 == QueryIntent.WHERE

    toks3 = tokenize("Who should I call when the server crashes?")
    intent3, _ = classify_query_intent(toks3, "Who should I call when the server crashes?")
    assert intent3 == QueryIntent.WHO
