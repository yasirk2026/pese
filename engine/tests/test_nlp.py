"""
Unit tests for PESE NLP modules: normalizer, stemmer, stopwords, tokenizer.
"""

from engine.nlp.normalizer import normalize_text, expand_contractions
from engine.nlp.stopwords import filter_stopwords, is_stopword
from engine.nlp.stemmer import stem_word, stem_words
from engine.nlp.tokenizer import tokenize, QueryRepresentation, generate_ngrams


def test_normalizer_contractions():
    text = "I don't think it's working when's the ride?"
    expanded = expand_contractions(text)
    assert "do not" in expanded
    assert "it is" in expanded
    assert "when is" in expanded


def test_normalizer_unicode():
    text = "BICYCLE café \t\n  ride   2024"
    normalized = normalize_text(text)
    assert normalized == "bicycle cafe ride 2024"


def test_stopwords_intent_preservation():
    tokens = ["when", "did", "i", "buy", "my", "bicycle"]
    filtered = filter_stopwords(tokens, preserve_intent=True)
    # 'when' is an intent word and must be preserved
    assert "when" in filtered
    # generic stopwords like 'did', 'my' should be filtered
    assert "did" not in filtered
    assert "my" not in filtered
    assert "buy" in filtered
    assert "bicycle" in filtered


def test_porter_stemmer():
    assert stem_word("bicycles") == "bicycl"
    assert stem_word("cycling") == "cycl"
    assert stem_word("learning") == "learn"
    assert stem_word("bought") == "bui"  # Irregular lemma mapping
    assert stem_word("went") == "go"


def test_tokenizer_and_query_representation():
    query = QueryRepresentation('when did I buy "my first bicycle"?')
    assert "when" in query.filtered_tokens
    assert "bui" in query.stems
    assert "my first bicycle" in query.phrases
    assert query.raw_query == 'when did I buy "my first bicycle"?'


def test_ngrams():
    tokens = ["clean", "bicycle", "chain", "oil"]
    bigrams = generate_ngrams(tokens, 2)
    assert "clean bicycle" in bigrams
    assert "chain oil" in bigrams
