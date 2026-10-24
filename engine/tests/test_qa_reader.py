"""
Unit & Integration Tests for PESE-QA-0 Neural Reading Comprehension Subsystem.
Verifies bidirectional attention, extractive dual span heads, answerability classification,
sliding window tokenizer fidelity, constrained span decoding, multi-passage arbitration,
and historical development regressions.
"""

import pytest
import torch
from engine.neural.configs.model_config import QAConfig, QATrainingConfig
from engine.neural.models.qa_reader import PESEQAReader
from engine.neural.tokenization.char_tokenizer import CharTokenizer
from engine.neural.tokenization.bpe_tokenizer import BPETokenizer
from engine.neural.data.contracts import QAExample
from engine.neural.data.qa_dataset import (
    tokenize_with_char_offsets,
    build_qa_features,
    ExtractiveQADataset
)
from engine.neural.inference.qa_reader import PESEQAInferenceReader, QAResult


@pytest.fixture
def mini_qa_reader():
    """Instantiate a lightweight PESE-QA-0 model with character tokenizer for deterministic testing."""
    tok = CharTokenizer()
    corpus = [
        "What is BM25F? BM25F is a fielded ranking algorithm.",
        "When was the project imagined? The search project was imagined in 2023.",
        "Tokyo is the capital of Japan."
    ]
    tok.train(corpus)

    cfg = QAConfig(
        model_name="PESE-QA-0-test",
        vocab_size=tok.vocab_size,
        d_model=64,
        n_layers=2,
        n_heads=2,
        d_ff=256,
        max_seq_len=64,
        dropout=0.0
    )
    model = PESEQAReader(cfg)
    reader = PESEQAInferenceReader(model, tok, answerability_threshold=0.50)
    return reader, model, tok, cfg


def test_qa_model_architecture_and_forward(mini_qa_reader):
    """Test model shapes, bidirectional attention, and loss computation."""
    _, model, _, cfg = mini_qa_reader

    B, T = 2, 32
    input_ids = torch.randint(0, cfg.vocab_size, (B, T), dtype=torch.long)
    token_type_ids = torch.zeros((B, T), dtype=torch.long)
    token_type_ids[:, 10:] = 1
    attention_mask = torch.ones((B, T), dtype=torch.long)

    # Test forward without targets
    start_logits, end_logits, ans_logits, loss = model(
        input_ids,
        token_type_ids=token_type_ids,
        attention_mask=attention_mask
    )

    assert start_logits.shape == (B, T)
    assert end_logits.shape == (B, T)
    assert ans_logits.shape == (B, 2)
    assert loss is None

    # Test forward with ground truth targets
    start_pos = torch.tensor([5, 12], dtype=torch.long)
    end_pos = torch.tensor([8, 15], dtype=torch.long)
    is_ans = torch.tensor([1, 1], dtype=torch.long)

    s_logits, e_logits, a_logits, total_loss = model(
        input_ids,
        token_type_ids=token_type_ids,
        attention_mask=attention_mask,
        start_positions=start_pos,
        end_positions=end_pos,
        is_answerable=is_ans
    )

    assert total_loss is not None
    assert total_loss.item() > 0.0
    assert not torch.isnan(total_loss)


def test_token_char_offset_fidelity(mini_qa_reader):
    """Verify that tokenize_with_char_offsets accurately traces subword spans back to characters."""
    _, _, tok, _ = mini_qa_reader

    text = "What is BM25F? The search project was in 2023."
    tokens, offsets = tokenize_with_char_offsets(text, tok)

    assert len(tokens) == len(offsets)
    for token_id, (cs, ce) in zip(tokens, offsets):
        assert ce > cs
        token_str = text[cs:ce]
        assert len(token_str) > 0
        # Decoding should reconstruct the slice
        decoded = tok.decode([token_id])
        assert decoded == token_str


def test_sliding_window_chunking():
    """Verify that passages exceeding max_seq_len are chunked with sliding window stride."""
    tok = CharTokenizer()
    tok.train(["abcdefghijklmnopqrstuvwxyz0123456789 .,!?-"])

    long_context = "Word " * 60 + "target answer " + "Tail " * 60
    start_char = long_context.find("target answer")
    end_char = start_char + len("target answer")

    ex = QAExample(
        id="chunk-test",
        question="What is the target?",
        context=long_context,
        answer_text="target answer",
        answer_start_char=start_char,
        answer_end_char=end_char,
        is_answerable=True
    )

    features = build_qa_features(ex, tok, max_seq_len=64, doc_stride=24)
    assert len(features) > 1

    # At least one window must contain the target answer
    answerable_feats = [f for f in features if f.is_answerable == 1]
    assert len(answerable_feats) >= 1
    target_feat = answerable_feats[0]
    assert target_feat.start_position > target_feat.context_token_start
    assert target_feat.end_position >= target_feat.start_position


@pytest.fixture(scope="module")
def checkpoint_reader(tmp_path_factory):
    from engine.evaluation.phase2f_support import build_engine
    eng = build_engine([], tmp_path_factory.mktemp("qa-checkpoint"), semantic=False)
    reader = eng._get_qa_reader()
    if reader is None:
        pytest.skip("Optional experimental QA checkpoint is not distributed with public source")
    return reader


def test_abstention_on_unanswerable_evidence(checkpoint_reader):
    """Verify that when evidence is absent, PESE-QA-0 strictly abstains (NO EVIDENCE = NO ANSWER)."""
    # Load production checkpoint
    reader = checkpoint_reader

    assert reader is not None

    question = "Who is the king of Mars?"
    passage = "BM25F is a fielded ranking algorithm that weights terms differently across title and body."

    res: QAResult = reader.read_passage(question, passage)

    assert res.answerable is False
    assert res.answer is None
    assert "NO EVIDENCE" in (res.abstention_reason or "")


def test_multi_passage_arbitration(checkpoint_reader):
    """Verify that read_candidate_passages selects the most supported passage and penalizes spam."""
    reader = checkpoint_reader

    question = "What is BM25F?"
    candidates = [
        {
            "passage_text": "Spam keyword stuffing buy cheap medicines online casino.",
            "final_score": 10.0,
            "passage_score": 1.0,
            "spam_penalty": 0.80,
            "doc_id": "spam-doc",
            "slug": "spam-doc"
        },
        {
            "passage_text": "BM25F stands for Best Matching 25 with Fields, an extension of Okapi BM25.",
            "final_score": 50.0,
            "passage_score": 15.0,
            "spam_penalty": 0.0,
            "doc_id": "bm25f-doc",
            "slug": "bm25f-doc"
        },
        {
            "passage_text": "Random notes from 2024 about buying groceries.",
            "final_score": 5.0,
            "passage_score": 0.5,
            "spam_penalty": 0.0,
            "doc_id": "grocery-doc",
            "slug": "grocery-doc"
        }
    ]

    res = reader.read_candidate_passages(question, candidates)
    assert res.answerable is True
    assert res.answer is not None
    assert any(term in res.answer for term in ["Okapi", "BM25", "Matching", "fielded", "ranking"])
    assert res.source_slug == "bm25f-doc"


def test_incorrect_experimental_shadow_cannot_overwrite_answer(tmp_path, monkeypatch):
    """Legacy model factual quality is evaluated separately, not a production contract.

    The old Yasir test failed because the experimental reader chose the later
    implementation date. Inject that same failure shape and prove isolation.
    """
    from engine.evaluation.phase2f_support import build_engine, document
    from engine.neural.inference.qa_reader import QAResult
    class WrongReader:
        def read_candidate_passages(self, query, passages):
            return QAResult(answer="October 2026", answerable=True, answer_confidence=0.99)
    eng = build_engine([document("nova", "NOVA", "NOVA launched in 2023. NOVA expanded in October 2026.")], tmp_path, semantic=False)
    monkeypatch.setattr(eng, "_get_qa_reader", lambda: WrongReader())
    deterministic = eng.search("when did NOVA launch", skip_qa=True)
    shadow = eng.search("when did NOVA launch", skip_qa=False)
    assert deterministic[0].featured_answer == shadow[0].featured_answer == "2023"
    assert shadow.qa_trace["shadow_answer"] == "October 2026"
    assert shadow.qa_trace["agreement"] == "NO"
