import re
import math
from collections import Counter

from job_bot.utils.logging import get_logger

logger = get_logger()

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "not", "no", "nor",
    "this", "that", "these", "those", "its", "just", "about", "very",
    "also", "only", "more", "some", "any", "each", "every", "both",
    "into", "over", "such", "than", "then", "from", "off", "down",
    "what", "which", "who", "whom", "when", "where", "why", "how",
    "all", "one", "two",
}


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if len(t) > 1 and t not in _STOPWORDS]


class BM25Scorer:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_count = 0
        self.avg_doc_len = 0.0
        self.doc_freq: Counter = Counter()
        self.doc_lens: list[int] = []
        self._term_counts: list[Counter] = []

    def fit(self, documents: list[str]):
        self.doc_count = len(documents)
        self._term_counts = []

        for doc in documents:
            tokens = _tokenize(doc)
            self.doc_lens.append(len(tokens))
            tc = Counter(tokens)
            self._term_counts.append(tc)
            for term in tc:
                self.doc_freq[term] += 1

        self.avg_doc_len = sum(self.doc_lens) / self.doc_count if self.doc_count else 1.0

    def scores(self, query: str) -> list[float]:
        qtokens = _tokenize(query)
        if not qtokens or not self.doc_count:
            return [0.0] * self.doc_count

        results = []
        for i in range(self.doc_count):
            doc_len = self.doc_lens[i]
            tc = self._term_counts[i]
            score = 0.0
            for qt in qtokens:
                df = self.doc_freq.get(qt, 0)
                if df == 0:
                    continue
                tf = tc.get(qt, 0)
                if tf == 0:
                    continue
                idf = math.log(
                    (self.doc_count - df + 0.5) / (df + 0.5) + 1.0
                )
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * doc_len / self.avg_doc_len
                )
                score += idf * numerator / denominator
            results.append(score)
        return results


def rank_opportunities(
    opportunities: list,
    profile: dict,
    top_n: int = 100,
) -> tuple[list, list[int]]:
    import time
    t0 = time.time()

    parts = []
    if profile.get("cv_text"):
        parts.append(profile["cv_text"])
    skills = profile.get("skills", [])
    if skills:
        parts.append(" ".join(skills))
    profile_text = " ".join(parts)

    if not profile_text.strip():
        return opportunities, list(range(min(top_n, len(opportunities))))

    docs = []
    for opp in opportunities:
        docs.append(" ".join([
            opp.title or "",
            opp.company or "",
            opp.description or "",
            opp.category or "",
        ]))

    scorer = BM25Scorer()
    scorer.fit(docs)
    all_scores = scorer.scores(profile_text)

    ranked = sorted(
        [(i, s) for i, s in enumerate(all_scores) if s > 0],
        key=lambda x: x[1],
        reverse=True,
    )
    top_indices = [i for i, _ in ranked[:top_n]]

    elapsed = time.time() - t0
    logger.info(
        "bm25_ranking",
        total=len(opportunities),
        top_n=len(top_indices),
        skipped=len(opportunities) - len(top_indices),
        elapsed_ms=round(elapsed * 1000),
    )

    return opportunities, top_indices
