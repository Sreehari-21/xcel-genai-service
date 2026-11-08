import re
from typing import List, Dict, Any, Optional, Tuple
from app.core.config import settings
from app.core.logging import log_event
from app.models.query import RetrievedChunk, SourceCitation
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store, ChromaVectorStore
from app.services.reranking_service import reranking_service
from app.services.structured_data_retriever import structured_retriever
from app.services.document_service import document_service

class QueryAnalysis:
    def __init__(self, query: str, query_type: str, has_numerical_filter: bool, detected_keywords: List[str]):
        self.query = query
        self.query_type = query_type  # 'general', 'pdf_only', 'csv_only', 'mixed', 'numerical'
        self.has_numerical_filter = has_numerical_filter
        self.detected_keywords = detected_keywords

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "query_type": self.query_type,
            "has_numerical_filter": self.has_numerical_filter,
            "detected_keywords": self.detected_keywords
        }

class UnifiedRetrievalService:
    def analyze_query(self, query: str, filters: Optional[Dict[str, Any]] = None) -> QueryAnalysis:
        q_lower = query.lower()
        
        # Check explicit filter first
        if filters and "source_type" in filters:
            st = filters["source_type"].lower()
            if st == "pdf":
                return QueryAnalysis(query, "pdf_only", False, ["source_filter:pdf"])
            elif st in ["csv", "csv_records"]:
                return QueryAnalysis(query, "csv_only", False, ["source_filter:csv"])

        # Check for numerical / relational operations
        num_match = bool(re.search(r'(?:above|below|greater|less|>|<|==|=|scored|marks|grade|salary|count)\s*\d+', q_lower))
        
        pdf_signals = ["document", "pdf", "chapter", "section", "page", "paragraph", "author", "definition", "concept", "theory", "explain", "describe", "meaning"]
        csv_signals = ["dataset", "csv", "table", "row", "record", "column", "who scored", "highest", "lowest", "average", "total", "list of students", "students", "marks", "database", "data"]

        pdf_hits = [w for w in pdf_signals if w in q_lower]
        csv_hits = [w for w in csv_signals if w in q_lower]

        if num_match:
            q_type = "numerical"
        elif pdf_hits and csv_hits:
            q_type = "mixed"
        elif "both" in q_lower or ("pdf" in q_lower and "csv" in q_lower):
            q_type = "mixed"
        elif pdf_hits and not csv_hits:
            q_type = "pdf_only"
        elif csv_hits and not pdf_hits:
            q_type = "csv_only"
        else:
            q_type = "mixed"  # default to unified hybrid retrieval across all sources

        return QueryAnalysis(
            query=query,
            query_type=q_type,
            has_numerical_filter=num_match,
            detected_keywords=pdf_hits + csv_hits
        )

    def retrieve(
        self,
        query: str,
        top_k: int = settings.top_k,
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[RetrievedChunk], str, List[SourceCitation], Dict[str, Any]]:
        """
        Unified multi-stage retrieval across PDF, CSV records, and CSV schemas.
        Returns:
            (top_chunks, formatted_context, citations, pipeline_trace)
        """
        log_event("QUERY", f"Processing query: '{query}' with top_k={top_k}, filters={filters}")
        
        # Stage 1: Query Analysis
        analysis = self.analyze_query(query, filters)
        log_event("QUERY", f"Query analysis result: {analysis.query_type}")

        # Generate query embedding
        query_embedding = embedding_service.embed_query(query)

        candidates: List[RetrievedChunk] = []
        pipeline_trace: Dict[str, Any] = {
            "query": query,
            "analysis": analysis.to_dict(),
            "pdf_candidates_count": 0,
            "csv_candidates_count": 0,
            "schema_candidates_count": 0,
            "structured_candidates_count": 0,
            "retrieved_candidates": []
        }

        # Stage 2: Vector retrieval per source type
        # 1. PDF retrieval (if not csv_only)
        if analysis.query_type != "csv_only":
            pdf_filters = {"document_name": filters.get("document_name")} if filters and "document_name" in filters else None
            pdf_chunks = vector_store.query(
                collection_name=ChromaVectorStore.COLLECTION_PDF,
                query_embedding=query_embedding,
                top_k=top_k,
                filters=pdf_filters
            )
            pipeline_trace["pdf_candidates_count"] = len(pdf_chunks)
            candidates.extend(pdf_chunks)

        # 2. CSV Vector retrieval (if not pdf_only)
        if analysis.query_type != "pdf_only":
            csv_filters = {"document_name": filters.get("file_name")} if filters and "file_name" in filters else None
            csv_chunks = vector_store.query(
                collection_name=ChromaVectorStore.COLLECTION_CSV_RECORDS,
                query_embedding=query_embedding,
                top_k=top_k,
                filters=csv_filters
            )
            pipeline_trace["csv_candidates_count"] = len(csv_chunks)
            candidates.extend(csv_chunks)

            # 3. CSV Schemas retrieval (crucial for structural schema questions)
            schema_chunks = vector_store.query(
                collection_name=ChromaVectorStore.COLLECTION_CSV_SCHEMAS,
                query_embedding=query_embedding,
                top_k=2,
                filters=None
            )
            pipeline_trace["schema_candidates_count"] = len(schema_chunks)
            candidates.extend(schema_chunks)

            # 4. Structured Pandas Retrieval for numerical/categorical filters
            # Check all registered CSV documents
            registered_docs = document_service.list_documents()
            csv_docs = [d for d in registered_docs if d.file_type == "csv"]
            structured_matches = []
            for d in csv_docs:
                matches = structured_retriever.retrieve(
                    query=query,
                    document_id=d.document_id,
                    file_name=d.file_name,
                    top_k=top_k
                )
                structured_matches.extend(matches)

            pipeline_trace["structured_candidates_count"] = len(structured_matches)
            candidates.extend(structured_matches)

        # Deduplicate candidates by chunk id
        seen_ids = set()
        deduped_candidates: List[RetrievedChunk] = []
        for c in candidates:
            if c.id not in seen_ids:
                seen_ids.add(c.id)
                deduped_candidates.append(c)

        # Stage 3: Reranking
        top_reranked = reranking_service.rerank(query, deduped_candidates, top_k=top_k)

        # Populate debug trace
        pipeline_trace["retrieved_candidates"] = [
            {
                "id": c.id,
                "score": c.score,
                "source_type": c.metadata.get("source_type", "unknown"),
                "document": c.metadata.get("document_name", "unknown"),
                "page": c.metadata.get("page_number"),
                "row": c.metadata.get("row_number"),
                "snippet": c.text[:120] + "..." if len(c.text) > 120 else c.text
            }
            for c in top_reranked
        ]

        # Stage 4: Context Construction & Citations
        context_parts = []
        citations: List[SourceCitation] = []
        seen_citations = set()

        for idx, chunk in enumerate(top_reranked, start=1):
            source_type = chunk.metadata.get("source_type", "document")
            doc_name = chunk.metadata.get("document_name", "unknown")
            doc_id = chunk.metadata.get("document_id", "")
            page_num = chunk.metadata.get("page_number")
            row_num = chunk.metadata.get("row_number")
            section = chunk.metadata.get("section")

            # Build context header according to spec
            if source_type == "pdf":
                header = f"SOURCE {idx}\nType: PDF\nDocument: {doc_name}\nPage: {page_num or 'N/A'}"
                if section:
                    header += f"\nSection: {section}"
            elif source_type == "csv":
                header = f"SOURCE {idx}\nType: CSV\nFile: {doc_name}\nRow: {row_num or 'N/A'}"
            elif source_type == "csv_schema":
                header = f"SOURCE {idx}\nType: CSV Dataset Schema\nFile: {doc_name}"
            else:
                header = f"SOURCE {idx}\nType: Document\nName: {doc_name}"

            context_parts.append(f"{header}\n\nContent:\n{chunk.text}\n")

            # Citation creation
            cit_key = f"{source_type}_{doc_name}_{page_num}_{row_num}"
            if cit_key not in seen_citations:
                seen_citations.add(cit_key)
                citations.append(
                    SourceCitation(
                        source_type=source_type,
                        file_name=doc_name,
                        document_id=doc_id,
                        page=page_num,
                        row=row_num,
                        chunk_id=chunk.id,
                        snippet=chunk.text[:150],
                        score=chunk.score
                    )
                )

        formatted_context = "\n---\n".join(context_parts)
        pipeline_trace["final_context_char_count"] = len(formatted_context)
        pipeline_trace["citations_count"] = len(citations)

        log_event(
            "RETRIEVAL",
            f"Retrieval complete: {len(top_reranked)} chunks formatted into context ({len(formatted_context)} chars)"
        )

        return top_reranked, formatted_context, citations, pipeline_trace

retrieval_service = UnifiedRetrievalService()
