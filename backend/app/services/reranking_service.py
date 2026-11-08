import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from app.core.logging import log_event
from app.models.query import RetrievedChunk

class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, candidates: List[RetrievedChunk], top_k: int) -> List[RetrievedChunk]:
        pass

class ModularReranker(BaseReranker):
    """
    Modular re-ranking service incorporating semantic similarity, lexical overlap,
    and structured match weighting.
    Can be seamlessly substituted with a Cross-Encoder, Cohere Rerank, or BGE Reranker.
    """
    def rerank(self, query: str, candidates: List[RetrievedChunk], top_k: int) -> List[RetrievedChunk]:
        if not candidates:
            return []

        log_event("RERANKING", f"Reranking {len(candidates)} candidates for top {top_k} selection")
        
        query_words = set(re.findall(r'\w+', query.lower()))
        # Remove very common stopwords
        stopwords = {"the", "a", "an", "is", "in", "it", "of", "and", "or", "for", "to", "what", "which", "who", "how"}
        informative_words = {w for w in query_words if w not in stopwords and len(w) > 2}

        scored_candidates = []
        for chunk in candidates:
            base_score = chunk.score
            chunk_text_lower = chunk.text.lower()
            
            # 1. Lexical word overlap boost
            overlap_score = 0.0
            if informative_words:
                matched_words = sum(1 for w in informative_words if w in chunk_text_lower)
                overlap_score = matched_words / len(informative_words)

            # 2. Exact substring match boost
            exact_boost = 0.15 if query.lower().strip() in chunk_text_lower else 0.0

            # 3. Structured retrieval boost (explicit conditions found)
            structured_boost = 0.1 if chunk.metadata.get("retrieval_method") == "structured_pandas" else 0.0

            # Combined weighted score
            final_score = (0.60 * base_score) + (0.25 * overlap_score) + exact_boost + structured_boost
            scored_candidates.append((round(min(1.0, final_score), 4), chunk))

        # Sort descending by final rerank score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        reranked_results: List[RetrievedChunk] = []
        for rank, (score, chunk) in enumerate(scored_candidates[:top_k], start=1):
            reranked_results.append(
                RetrievedChunk(
                    id=chunk.id,
                    text=chunk.text,
                    metadata=chunk.metadata,
                    score=score,
                    rank=rank
                )
            )

        log_event("RERANKING", f"Completed reranking; returned {len(reranked_results)} top chunks")
        return reranked_results

reranking_service = ModularReranker()
