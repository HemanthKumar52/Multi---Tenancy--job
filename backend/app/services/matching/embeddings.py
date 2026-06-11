"""Embeddings with an offline, dependency-light default.

In dev we use a deterministic feature-hashing bag-of-words embedding (no network, no model
download) — good enough for cosine similarity ranking. In prod, swap ``embed`` for a real
provider (e.g. Voyage) behind the same interface; pgvector stores the vectors.
"""
from __future__ import annotations

import hashlib

import numpy as np

from app.services.common.text import content_tokens

_DIM = 512


def _stable_hash(token: str) -> int:
    # Deterministic across processes (unlike built-in hash()), so stored vectors stay valid.
    return int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")


def embed(text: str) -> np.ndarray:
    """Hash tokens into a fixed-dim L2-normalized vector."""
    vec = np.zeros(_DIM, dtype=np.float32)
    for tok in content_tokens(text):
        h = _stable_hash(tok)
        idx = h % _DIM
        sign = 1.0 if (h >> 16) & 1 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    return vec / norm if norm else vec


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))
