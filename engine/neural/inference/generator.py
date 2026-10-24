"""
PESE Neural Genesis: Autoregressive Inference Generator
Provides text completion via PESETransformer with decoding strategies,
temperature scaling, and explicit experimental guardrails.
"""

from typing import Dict, Any, Optional
import torch

from ..models.transformer import PESETransformer
from ..tokenization.base import BaseTokenizer


class NeuralGenerator:
    """
    Experimental inference interface for PESE Neural Genesis models.
    """

    def __init__(self, model: PESETransformer, tokenizer: BaseTokenizer):
        self.model = model
        self.tokenizer = tokenizer
        self.model.eval()

    @torch.no_grad()
    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 40,
        temperature: float = 0.8,
        top_k: Optional[int] = 40
    ) -> Dict[str, Any]:
        """
        Generate continuation from prompt string.
        """
        # Encode prompt without adding trailing EOS
        token_ids = self.tokenizer.encode(prompt, add_special_tokens=False)
        if not token_ids:
            token_ids = [self.tokenizer.bos_token_id]

        input_tensor = torch.tensor([token_ids], dtype=torch.long, device=next(self.model.parameters()).device)
        generated_indices = self.model.generate(
            input_tensor,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_k=top_k
        )

        all_tokens = generated_indices[0].tolist()
        new_token_ids = all_tokens[len(token_ids):]

        generated_text = self.tokenizer.decode(new_token_ids, skip_special_tokens=True)
        full_text = prompt + generated_text

        return {
            "prompt": prompt,
            "generated_text": generated_text,
            "full_text": full_text,
            "tokens_generated": len(new_token_ids),
            "temperature": temperature,
            "top_k": top_k,
            "model_name": self.model.config.model_name,
            "experimental": True,
            "disclaimer": "Output produced by experimental PESE-NG-0 model. Not verified against corpus evidence."
        }
