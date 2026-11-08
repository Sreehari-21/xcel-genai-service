import json
import os
import pytest
from app.services.retrieval_service import retrieval_service

def calculate_retrieval_metrics(questions_file: str, top_k: int = 5):
    """
    Evaluates Hit@K and Mean Reciprocal Rank (MRR) for the evaluation dataset.
    """
    with open(questions_file, "r") as f:
        dataset = json.load(f)

    hits = 0
    reciprocal_ranks = []

    for item in dataset:
        q = item["question"]
        expected_src = item["expected_source"].lower()
        expected_type = item.get("expected_source_type", "").lower()

        top_chunks, _, _, _ = retrieval_service.retrieve(query=q, top_k=top_k)

        found_rank = None
        for rank, chunk in enumerate(top_chunks, start=1):
            doc_name = str(chunk.metadata.get("document_name", "")).lower()
            src_type = str(chunk.metadata.get("source_type", "")).lower()

            # Check match against expected document or expected source type
            if expected_src in doc_name or (expected_type and expected_type == src_type):
                found_rank = rank
                break

        if found_rank is not None:
            hits += 1
            reciprocal_ranks.append(1.0 / found_rank)
        else:
            reciprocal_ranks.append(0.0)

    total = len(dataset)
    hit_at_k = hits / total if total > 0 else 0.0
    mrr = sum(reciprocal_ranks) / total if total > 0 else 0.0

    return {
        "total_queries": total,
        "top_k": top_k,
        "hits": hits,
        "hit_at_k": round(hit_at_k, 4),
        "mrr": round(mrr, 4)
    }

def test_evaluation_pipeline():
    eval_file = os.path.join(os.path.dirname(__file__), "evaluation_questions.json")
    metrics = calculate_retrieval_metrics(eval_file, top_k=5)
    print(f"\nEvaluation Results: Hit@5 = {metrics['hit_at_k']:.2%}, MRR = {metrics['mrr']:.4f}")
    assert metrics["total_queries"] > 0
    # Hit@5 should be high on valid indexed datasets
    assert metrics["hit_at_k"] >= 0.5
