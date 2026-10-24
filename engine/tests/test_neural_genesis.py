"""
PESE Unit & Integration Tests: Neural Genesis Subsystem (Phase 2C)
"""

import tempfile
from pathlib import Path
import pytest
import torch

from engine.neural.configs.model_config import TransformerConfig, TrainingConfig
from engine.neural.tokenization.char_tokenizer import CharTokenizer
from engine.neural.tokenization.bpe_tokenizer import BPETokenizer
from engine.neural.models.attention import MultiHeadSelfAttention
from engine.neural.models.ffn import FeedForward
from engine.neural.models.transformer_block import TransformerBlock
from engine.neural.models.transformer import PESETransformer
from engine.neural.models.registry import ModelRegistry, ModelCard, ModelStatus
from engine.neural.data.contracts import find_answer_span, export_faqs_to_qa_contracts, QAExample, RerankerPair
from engine.neural.data.dataset import MICRO_OVERFIT_TEXTS, SYNTHETIC_PUBLIC_CORPUS, CausalLMDataset
from engine.neural.training.checkpoint import save_checkpoint, load_checkpoint


def test_transformer_config_parameter_counting():
    cfg = TransformerConfig(
        vocab_size=256,
        d_model=128,
        n_layers=4,
        n_heads=4,
        d_ff=512,
        max_seq_len=128
    )
    analytical_count = cfg.count_parameters()
    model = PESETransformer(cfg)
    actual_count = model.count_parameters()
    assert analytical_count == actual_count
    assert 500_000 <= actual_count <= 2_000_000


def test_char_tokenizer():
    tok = CharTokenizer()
    texts = ["hello world", "neural genesis"]
    tok.train(texts)
    assert tok.vocab_size > 10

    encoded = tok.encode("hello", add_special_tokens=True)
    assert encoded[0] == tok.bos_token_id
    assert encoded[-1] == tok.eos_token_id

    decoded = tok.decode(encoded, skip_special_tokens=True)
    assert decoded == "hello"


def test_bpe_tokenizer():
    tok = BPETokenizer()
    corpus = [
        "the quick brown fox jumps over the lazy dog",
        "quick brown foxes jump high",
        "lazy dogs sleep all day long"
    ]
    tok.train(corpus, target_vocab_size=80, min_frequency=1)
    assert tok.vocab_size <= 80

    encoded = tok.encode("quick brown dog", add_special_tokens=False)
    decoded = tok.decode(encoded, skip_special_tokens=True)
    assert decoded.strip() == "quick brown dog"


def test_multi_head_attention_causal_shape():
    cfg = TransformerConfig(vocab_size=100, d_model=64, n_heads=4, max_seq_len=32)
    attn = MultiHeadSelfAttention(cfg)

    x = torch.randn(2, 16, 64)
    out = attn(x)
    assert out.shape == (2, 16, 64)


def test_transformer_block_shape():
    cfg = TransformerConfig(vocab_size=100, d_model=64, n_heads=4, d_ff=256, max_seq_len=32)
    block = TransformerBlock(cfg)

    x = torch.randn(2, 16, 64)
    out = block(x)
    assert out.shape == (2, 16, 64)


def test_transformer_forward_and_loss():
    cfg = TransformerConfig(vocab_size=128, d_model=64, n_layers=2, n_heads=2, max_seq_len=32)
    model = PESETransformer(cfg)

    idx = torch.randint(0, 128, (2, 16))
    targets = torch.randint(0, 128, (2, 16))

    logits, loss = model(idx, targets=targets)
    assert logits.shape == (2, 16, 128)
    assert loss is not None
    assert loss.item() > 0.0
    assert not torch.isnan(loss)


def test_transformer_generation():
    cfg = TransformerConfig(vocab_size=128, d_model=64, n_layers=2, n_heads=2, max_seq_len=32)
    model = PESETransformer(cfg)

    prompt = torch.tensor([[1, 2, 3]], dtype=torch.long)
    generated = model.generate(prompt, max_new_tokens=5, temperature=1.0)
    assert generated.shape == (1, 8)
    assert generated[0, :3].tolist() == [1, 2, 3]


def test_qa_span_localization_and_abstention():
    context = "The capital of Japan is Tokyo, known for its vibrant technology sector."
    answer = "Tokyo"

    tok = CharTokenizer()
    tok.train([context])

    span = find_answer_span(context, answer, tok)
    assert span["found"] is True
    assert context[span["start_char"]:span["end_char"]] == answer
    assert span["start_token"] is not None

    unanswerable = find_answer_span(context, "Atlantis", tok)
    assert unanswerable["found"] is False
    assert unanswerable["start_char"] is None


def test_faq_to_qa_export():
    sample_docs = [
        {
            "id": "doc-japanese",
            "title": "Japanese Guide",
            "content": "Hiragana has 46 characters. Katakana has 46 characters.",
            "faqs": [
                {
                    "question": "How many hiragana characters exist?",
                    "answer": "Hiragana has 46 characters"
                }
            ]
        }
    ]

    qa_list = export_faqs_to_qa_contracts(sample_docs, include_negative_abstentions=True)
    assert len(qa_list) == 2  # 1 answerable FAQ + 1 negative abstention

    ans_qa = qa_list[0]
    assert ans_qa.is_answerable is True
    assert ans_qa.answer_start_char is not None

    neg_qa = qa_list[1]
    assert neg_qa.is_answerable is False
    assert neg_qa.abstention_reason == "NO EVIDENCE = NO ANSWER"


def test_checkpoint_save_and_reload():
    cfg = TransformerConfig(vocab_size=64, d_model=32, n_layers=1, n_heads=2, max_seq_len=16)
    model = PESETransformer(cfg)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        chk_file = save_checkpoint(
            model=model,
            optimizer=None,
            config=cfg.model_dump(),
            step=10,
            loss=2.5,
            checkpoint_dir=tmp_path
        )
        assert chk_file.exists()

        loaded_model, chk_data = load_checkpoint(chk_file, device="cpu")
        assert chk_data["step"] == 10
        assert chk_data["loss"] == 2.5
        assert loaded_model.config.vocab_size == 64


def test_model_registry():
    custom_registry = ModelRegistry()
    models = custom_registry.list_models()
    assert len(models) >= 1

    ng0 = custom_registry.get("PESE-NG-0")
    assert ng0 is not None
    assert ng0.status == ModelStatus.EXPERIMENT
    assert ng0.allowed_for_ranking is False
    assert ng0.allowed_for_answers is False


def test_privacy_boundary_assurance():
    corpus_joined = " ".join(SYNTHETIC_PUBLIC_CORPUS).lower()
    # Ensure zero private search queries or private user paths are in the synthetic corpus
    forbidden = ["private", "password", "confidential", "api_key", "secret"]
    for word in forbidden:
        assert word not in corpus_joined, f"Privacy leak: found '{word}' in public synthetic corpus"
