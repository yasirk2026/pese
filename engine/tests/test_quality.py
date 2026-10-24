"""
Unit tests for PESE Quality and Spam Detector.
"""

from engine.indexing.document import Document
from engine.quality.spam_detector import SpamDetector
from engine.quality.quality_signals import QualitySignalScorer


def test_keyword_stuffing_detection():
    # Page repeating 'bicycle' dozens of times
    stuffed_body = "bicycle " * 45 + "deal cheap store sale pedals wheels price buy"
    spam_doc = Document(
        id="spam-1",
        slug="spam-bicycle",
        title="Bicycle Deals Bicycle Cheap",
        content=stuffed_body,
    )
    detector = SpamDetector()
    evaluation = detector.evaluate_document(spam_doc)

    assert evaluation["is_spam"] is True
    assert evaluation["spam_penalty"] >= 0.80
    assert any("Keyword stuffing detected" in r for r in evaluation["reasons"])


def test_clean_document_no_penalty():
    clean_body = """# Bicycle Journey
Last spring I decided to purchase a commuter bicycle. The local shop had a wide range
of frames and components. I tested steel and aluminum options before making my final choice.
Daily riding has completely transformed how I move around town.
"""
    clean_doc = Document(
        id="clean-1",
        slug="clean-bicycle",
        title="My Bicycle Journey",
        content=clean_body,
    )
    detector = SpamDetector()
    evaluation = detector.evaluate_document(clean_doc)

    assert evaluation["is_spam"] is False
    assert evaluation["spam_penalty"] == 0.0


def test_short_content_is_not_automatically_spam():
    thin_doc = Document(
        id="thin-1",
        slug="thin-page",
        title="Thin Page",
        content="Just four words here.",
    )
    detector = SpamDetector()
    evaluation = detector.evaluate_document(thin_doc)

    assert evaluation["spam_penalty"] == 0.0
    assert evaluation["is_spam"] is False


def test_quality_scorer():
    doc = Document(
        id="q-doc",
        slug="q-doc",
        title="Quality Document",
        meta_description="Informative meta description describing the topic in good detail.",
        content="""# Heading One
Substantial paragraph with good vocabulary explaining the subject matter clearly.

## Heading Two
Another paragraph discussing further nuances and linking to [Another](/doc/another).
"""
    )
    scorer = QualitySignalScorer()
    res = scorer.compute_quality(doc)
    assert res["quality_score"] >= 0.6
