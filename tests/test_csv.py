import os
import pytest
import pandas as pd
from app.core.config import settings
from app.services.csv_service import csv_service
from app.services.structured_data_retriever import structured_retriever

@pytest.fixture
def sample_csv_path(tmp_path):
    csv_file = tmp_path / "students.csv"
    data = """student_id,name,semester,subject,marks
101,Akhil,6,DBMS,85
102,Rahul,6,DBMS,72
103,Anu,6,DBMS,95
104,Priya,6,OS,88
105,Sneha,6,DBMS,92
"""
    csv_file.write_text(data)
    yield str(csv_file)
    structured_retriever.invalidate_cache("csv_test_1")
    processed_csv = os.path.join(settings.processed_dir, "csv_test_1.csv")
    if os.path.exists(processed_csv):
        os.remove(processed_csv)

def test_csv_schema_and_record_generation(sample_csv_path):
    processed = csv_service.parse_csv(
        file_path=sample_csv_path,
        document_id="csv_test_1",
        file_name="students.csv"
    )
    
    assert processed.row_count == 5
    assert len(processed.record_chunks) == 5
    assert processed.schema_chunk is not None
    assert "students.csv" in processed.schema_text
    assert "student_id" in processed.column_types
    assert "marks" in processed.column_types
    
    # Check row text format
    first_record = processed.record_chunks[0]
    assert "Student Id: 101" in first_record.text
    assert "Marks: 85" in first_record.text
    assert first_record.metadata.source_type == "csv"
    assert first_record.metadata.row_number == 1
    assert first_record.metadata.document_name == "students.csv"

def test_structured_numerical_retrieval(sample_csv_path):
    # Process to ensure CSV is cached in processed_dir
    processed = csv_service.parse_csv(
        file_path=sample_csv_path,
        document_id="csv_test_1",
        file_name="students.csv"
    )
    
    # Query for students scored above 90 in DBMS
    results = structured_retriever.retrieve(
        query="Which students scored above 90 in DBMS?",
        document_id="csv_test_1",
        file_name="students.csv",
        top_k=5
    )
    
    assert len(results) == 2  # Anu (95) and Sneha (92)
    texts = [r.text for r in results]
    assert any("Anu" in t for t in texts)
    assert any("Sneha" in t for t in texts)
    assert not any("Rahul" in t for t in texts)  # Rahul scored 72
