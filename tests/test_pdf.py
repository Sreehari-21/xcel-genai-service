import os
import pytest
import pymupdf
from app.services.pdf_service import pdf_parser
from app.services.chunking_service import chunking_service

@pytest.fixture
def sample_pdf_path(tmp_path):
    pdf_file = tmp_path / "test_dbms.pdf"
    doc = pymupdf.open()
    
    # Page 1
    page1 = doc.new_page()
    page1.insert_text(
        (50, 72),
        "Database Management Systems\n\n"
        "Chapter 3: Normalization\n"
        "Normalization is the process of organizing data in a database to eliminate redundancy.\n"
        "It involves decomposing tables to avoid insertion, update, and deletion anomalies.\n\n"
        "First Normal Form (1NF)\n"
        "A relation is in 1NF if every attribute contains only atomic, indivisible values.\n\n"
        "Second Normal Form (2NF)\n"
        "A relation is in 2NF if it is in 1NF and no non-prime attribute depends on a proper subset of any candidate key.",
        fontsize=12
    )

    # Page 2
    page2 = doc.new_page()
    page2.insert_text(
        (50, 72),
        "Third Normal Form (3NF)\n"
        "A relation is in 3NF if it is in 2NF and no non-prime attribute is transitively dependent on the primary key.\n\n"
        "Boyce-Codd Normal Form (BCNF)\n"
        "A relation is in BCNF if for every functional dependency X -> Y, X is a superkey.",
        fontsize=12
    )

    doc.save(str(pdf_file))
    doc.close()
    return str(pdf_file)

def test_pdf_extraction(sample_pdf_path):
    extracted = pdf_parser.parse(
        file_path=sample_pdf_path,
        document_id="doc_test_1",
        document_name="test_dbms.pdf"
    )
    assert extracted.document_id == "doc_test_1"
    assert extracted.document_name == "test_dbms.pdf"
    assert extracted.total_pages == 2
    assert len(extracted.sections) > 0

def test_structure_aware_chunking(sample_pdf_path):
    extracted = pdf_parser.parse(
        file_path=sample_pdf_path,
        document_id="doc_test_1",
        document_name="test_dbms.pdf"
    )
    chunks = chunking_service.chunk_pdf(extracted)
    
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.metadata.source_type == "pdf"
        assert chunk.metadata.document_id == "doc_test_1"
        assert chunk.metadata.document_name == "test_dbms.pdf"
        assert chunk.metadata.page_number in [1, 2]
        assert chunk.metadata.chunk_id.startswith("doc_test_1_chunk_")
        assert len(chunk.text) > 0

def test_empty_pdf_rejection(tmp_path):
    empty_pdf = tmp_path / "empty.pdf"
    doc = pymupdf.open()
    doc.new_page()  # Blank page with no text
    doc.save(str(empty_pdf))
    doc.close()

    with pytest.raises(ValueError):
        pdf_parser.parse(str(empty_pdf), "doc_empty", "empty.pdf")

