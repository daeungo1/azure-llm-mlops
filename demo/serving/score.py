"""Offline CPU embeddings and intent routing for English synthetic telco tickets."""

import json
import logging
import os
import time
from pathlib import Path

import numpy as np

LOGGER = logging.getLogger(__name__)
CATEGORIES = {
    "billing": "An incorrect invoice, unexpected charges, refund or payment problem.",
    "network": "Slow mobile data, no internet connection, poor signal or dropped calls.",
    "cancellation": "Cancel my subscription, close my account or switch to another carrier.",
}
_tokenizer = None
_model = None
_prototypes = None


def parse_request(raw_data: str) -> list[str]:
    body = json.loads(raw_data)
    if not isinstance(body, dict) or set(body) != {"texts"}:
        raise ValueError("Expected an object containing only the 'texts' field.")
    texts = body["texts"]
    if not isinstance(texts, list) or not 1 <= len(texts) <= 16:
        raise ValueError("'texts' must be an array of 1 to 16 strings.")
    if any(not isinstance(text, str) or not text.strip() or len(text) > 2000 for text in texts):
        raise ValueError("Each text must be non-blank and at most 2000 characters.")
    return texts


def embed(texts: list[str]) -> np.ndarray:
    import torch

    tokens = _tokenizer(texts, padding=True, truncation=True, max_length=256, return_tensors="pt")
    with torch.inference_mode():
        hidden = _model(**tokens).last_hidden_state
        mask = tokens["attention_mask"].unsqueeze(-1).to(hidden.dtype)
        pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
        return torch.nn.functional.normalize(pooled, p=2, dim=1).cpu().numpy()


def init() -> None:
    global _tokenizer, _model, _prototypes
    import torch
    from transformers import AutoModel, AutoTokenizer

    torch.set_num_threads(2)
    root = Path(os.environ["AZUREML_MODEL_DIR"])
    models = list(root.rglob("config.json"))
    model_dirs = [path.parent for path in models if (path.parent / "model.safetensors").exists()]
    if len(model_dirs) != 1:
        raise RuntimeError(f"Expected exactly one packaged HF model, found {len(model_dirs)}.")
    _tokenizer = AutoTokenizer.from_pretrained(model_dirs[0], local_files_only=True)
    _model = AutoModel.from_pretrained(
        model_dirs[0], local_files_only=True, use_safetensors=True, trust_remote_code=False
    ).eval()
    _prototypes = embed(list(CATEGORIES.values()))
    LOGGER.info("Loaded local CPU model; no Hugging Face network access is needed at inference.")


def run(raw_data: str):
    started = time.perf_counter()
    try:
        texts = parse_request(raw_data)
    except ValueError as error:
        from azureml_inference_server_http.api.aml_response import AMLResponse

        LOGGER.warning("Rejected invalid scoring request: %s", error)
        return AMLResponse({"error": str(error)}, 400)
    similarities = embed(texts) @ _prototypes.T
    labels = list(CATEGORIES)
    predictions = [
        {
            "intent": labels[int(np.argmax(scores))],
            "similarities": {
                label: round(float(value), 6) for label, value in zip(labels, scores, strict=True)
            },
        }
        for scores in similarities
    ]
    LOGGER.info("Scored %d tickets in %.3f seconds.", len(texts), time.perf_counter() - started)
    return {
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "embedding_dimension": 384,
        "predictions": predictions,
    }
