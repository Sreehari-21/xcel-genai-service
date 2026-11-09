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
    technical acronym boosting, section heading alignment, and structured match weighting.
    Can be seamlessly substituted with a Cross-Encoder, Cohere Rerank, or BGE Reranker.
    """
    def rerank(self, query: str, candidates: List[RetrievedChunk], top_k: int) -> List[RetrievedChunk]:
        if not candidates:
            return []

        log_event("RERANKING", f"Reranking {len(candidates)} candidates for top {top_k} selection")
        
        query_lower = query.lower().strip()
        query_words = set(re.findall(r'\w+', query_lower))
        stopwords = {
            "the", "a", "an", "is", "in", "it", "of", "and", "or", "for", "to",
            "what", "which", "who", "how", "according", "are", "were", "was",
            "does", "did", "can", "tell", "give", "show", "from", "with", "this"
        }
        informative_words = {w for w in query_words if w not in stopwords and len(w) > 1}
        
        # High-signal domain terms and technical acronyms (e.g. 1nf, 2nf, 3nf, bcnf, sql, dbms, acid)
        technical_acronyms = {w for w in informative_words if any(c.isdigit() for c in w) or w in {"sql", "dbms", "bcnf", "acid"}}

        scored_candidates = []
        for chunk in candidates:
            base_score = chunk.score
            chunk_text_lower = chunk.text.lower()
            section_lower = str(chunk.metadata.get("section", "")).lower()
            
            # 1. Lexical word overlap boost
            overlap_score = 0.0
            if informative_words:
                matched_words = sum(1 for w in informative_words if w in chunk_text_lower)
                overlap_score = matched_words / len(informative_words)

            # 2. Technical acronym and exact domain code boost (Crucial for factual queries like 1NF, 2NF, BCNF)
            acronym_boost = 0.0
            if technical_acronyms:
                matched_acronyms = sum(
                    1 for a in technical_acronyms if a in chunk_text_lower or a in section_lower
                )
                acronym_boost = (matched_acronyms / len(technical_acronyms)) * 0.25

            # 3. Section heading alignment boost
            section_boost = 0.0
            if section_lower and informative_words:
                matched_section_words = sum(1 for w in informative_words if w in section_lower)
                if matched_section_words > 0:
                    section_boost = min(0.20, (matched_section_words / len(informative_words)) * 0.25)

            # 4. Exact substring match boost
            clean_query = re.sub(r'[^\w\s]', '', query_lower)
            exact_boost = 0.15 if (query_lower in chunk_text_lower or (len(clean_query) > 10 and clean_query in chunk_text_lower)) else 0.0

            # 5. Structured retrieval boost (explicit conditions found)
            structured_boost = 0.12 if chunk.metadata.get("retrieval_method") == "structured_pandas" else 0.0

            # Combined weighted score (Dense similarity 45% + Lexical 25% + Technical & Section boosts)
            final_score = (
                (0.45 * base_score)
                + (0.25 * overlap_score)
                + acronym_boost
                + section_boost
                + exact_boost
                + structured_boost
            )
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
