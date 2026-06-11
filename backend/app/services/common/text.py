"""Lightweight text utilities: tokenization, keyword + skill extraction.

Zero external NLP deps so the core runs offline. ``SKILL_VOCAB`` lets us recognize
common multi-word skills ("machine learning") that naive unigram tokenization would miss.
"""
from __future__ import annotations

import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9.+#-]*")

STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "are", "will", "have", "has", "this",
    "that", "from", "they", "their", "them", "who", "all", "can", "able", "into", "out", "per",
    "etc", "via", "but", "not", "any", "may", "should", "must", "such", "use", "using", "used",
    "work", "working", "team", "teams", "role", "job", "we", "us", "is", "of", "to", "in", "on",
    "as", "an", "at", "by", "or", "be", "a", "i", "it", "if", "do", "so", "up", "we're", "you'll",
    "experience", "years", "year", "strong", "excellent", "good", "great", "looking", "seeking",
    "responsibilities", "requirements", "qualifications", "preferred", "plus", "ability",
}

# A pragmatic vocabulary of common skills (esp. multi-word ones). Extend freely / load from DB.
SKILL_VOCAB = {
    "python", "java", "javascript", "typescript", "go", "golang", "rust", "c++", "c#", "ruby",
    "php", "kotlin", "swift", "scala", "sql", "nosql", "bash", "r",
    "react", "next.js", "nextjs", "vue", "angular", "svelte", "node.js", "nodejs", "express",
    "fastapi", "django", "flask", "spring", "rails", ".net", "tailwind",
    "postgresql", "postgres", "mysql", "mongodb", "redis", "elasticsearch", "kafka", "rabbitmq",
    "snowflake", "clickhouse", "duckdb", "dynamodb", "cassandra",
    "aws", "gcp", "azure", "docker", "kubernetes", "k8s", "terraform", "ansible", "helm",
    "jenkins", "github actions", "ci/cd", "linux",
    "machine learning", "deep learning", "nlp", "computer vision", "pytorch", "tensorflow",
    "scikit-learn", "pandas", "numpy", "spark", "airflow", "dbt", "etl", "data engineering",
    "llm", "langchain", "langgraph", "rag", "transformers", "openai", "anthropic",
    "rest", "graphql", "grpc", "microservices", "playwright", "selenium", "pytest", "jest",
    "agile", "scrum", "figma", "git", "oauth", "jwt",
}

# Longest-first so multi-word skills match before their constituent words.
_SKILL_VOCAB_SORTED = sorted(SKILL_VOCAB, key=len, reverse=True)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def content_tokens(text: str) -> list[str]:
    return [t for t in tokenize(text) if t not in STOPWORDS and len(t) > 1]


def extract_keywords(text: str, top_n: int = 25) -> list[str]:
    """Frequency-ranked content keywords."""
    counts = Counter(content_tokens(text))
    return [w for w, _ in counts.most_common(top_n)]


def extract_skills(text: str) -> list[str]:
    """Skills present in ``text`` according to SKILL_VOCAB (multi-word aware)."""
    low = " " + text.lower() + " "
    found: list[str] = []
    for skill in _SKILL_VOCAB_SORTED:
        # word-ish boundary match to avoid 'r' matching inside words, etc.
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        if re.search(pattern, low):
            found.append(skill)
    # de-dup preserving order
    seen: set[str] = set()
    return [s for s in found if not (s in seen or seen.add(s))]
