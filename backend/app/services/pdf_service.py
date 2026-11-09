import os
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pymupdf
from app.core.logging import log_event

class ExtractedSection:
    def __init__(self, page_number: int, heading: Optional[str], content: str, section_type: str = "text"):
        self.page_number = page_number
        self.heading = heading
        self.content = content
        self.section_type = section_type  # text, table, list, etc.

class ExtractedPDFDocument:
    def __init__(self, document_id: str, document_name: str, total_pages: int, sections: List[ExtractedSection]):
        self.document_id = document_id
        self.document_name = document_name
        self.total_pages = total_pages
        self.sections = sections

class BasePDFParser(ABC):
    @abstractmethod
    def parse(self, file_path: str, document_id: str, document_name: str) -> ExtractedPDFDocument:
        pass

class PyMuPDFParser(BasePDFParser):
    def parse(self, file_path: str, document_id: str, document_name: str) -> ExtractedPDFDocument:
        log_event("PDF EXTRACTION", f"Opening PDF: {document_name} at {file_path}")
        try:
            doc = pymupdf.open(file_path)
        except Exception as e:
            raise ValueError(f"Failed to open PDF document: {str(e)}")

        if doc.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported. Please provide an unencrypted PDF.")

        total_pages = len(doc)
        if total_pages == 0:
            raise ValueError("The provided PDF contains 0 pages.")

        sections: List[ExtractedSection] = []
        total_extracted_chars = 0
        current_heading = "General"

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = doc[page_idx]
            
            # 1. Extract any tabular data on the page
            page_table_texts = []
            try:
                tables = page.find_tables()
                if tables and tables.tables:
                    for table in tables.tables:
                        try:
                            # Generate markdown-formatted table
                            table_df = table.extract()
                            if table_df and len(table_df) > 1:
                                headers = [str(c or "").strip() for c in table_df[0]]
                                rows = table_df[1:]
                                md_rows = [" | ".join(headers)]
                                md_rows.append(" | ".join(["---"] * len(headers)))
                                for r in rows:
                                    md_rows.append(" | ".join([str(cell or "").strip() for cell in r]))
                                table_str = "\n".join(md_rows)
                                page_table_texts.append(table_str)
                                sections.append(
                                    ExtractedSection(
                                        page_number=page_num,
                                        heading=f"{current_heading} (Table)",
                                        content=table_str,
                                        section_type="table"
                                    )
                                )
                        except Exception:
                            pass
            except Exception:
                pass

            # 2. Extract structured blocks with typography/heading analysis
            try:
                page_dict = page.get_text("dict")
                blocks = page_dict.get("blocks", [])
            except Exception:
                blocks = []

            for b in blocks:
                # Type 0 is text block
                if b.get("type") == 0:
                    block_text_lines = []
                    block_max_font_size = 0.0
                    is_bold = False

                    for line in b.get("lines", []):
                        line_text = ""
                        for span in line.get("spans", []):
                            span_text = span.get("text", "").strip()
                            if span_text:
                                line_text += (" " + span_text if line_text else span_text)
                                size = span.get("size", 0.0)
                                if size > block_max_font_size:
                                    block_max_font_size = size
                                flags = span.get("flags", 0)
                                if flags & 2 or "bold" in span.get("font", "").lower():
                                    is_bold = True
                        if line_text:
                            block_text_lines.append(line_text)

                    full_block_text = "\n".join(block_text_lines).strip()
                    if not full_block_text:
                        continue

                    total_extracted_chars += len(full_block_text)

                    # Heading heuristic: font size noticeably larger than 11pt, bold short line, or numbered section title
                    first_line = block_text_lines[0].strip() if block_text_lines else ""
                    is_numbered_title = bool(
                        re.match(r"^(?:\d+\.|\d+\.\d+|Chapter\s+\d+|Section\s+\d+)\s+[A-Za-z]", first_line)
                        and len(first_line) < 120
                        and not first_line.endswith(".")
                    )

                    is_heading_candidate = (
                        (block_max_font_size >= 13.0 or (is_bold and len(full_block_text) < 120) or is_numbered_title)
                        and len(full_block_text.splitlines()) <= 2
                        and not full_block_text.endswith(".")
                    )

                    if is_heading_candidate and len(full_block_text) < 150:
                        current_heading = full_block_text.strip()
                        sections.append(
                            ExtractedSection(
                                page_number=page_num,
                                heading=current_heading,
                                content=full_block_text,
                                section_type="heading"
                            )
                        )
                    elif is_numbered_title and len(block_text_lines) > 1:
                        # Block begins with a numbered section title followed by body text
                        current_heading = first_line
                        sections.append(
                            ExtractedSection(
                                page_number=page_num,
                                heading=current_heading,
                                content=first_line,
                                section_type="heading"
                            )
                        )
                        remaining_text = "\n".join(block_text_lines[1:]).strip()
                        if remaining_text:
                            is_list = any(line.strip().startswith(("-", "*", "•")) for line in block_text_lines[1:])
                            sections.append(
                                ExtractedSection(
                                    page_number=page_num,
                                    heading=current_heading,
                                    content=remaining_text,
                                    section_type="list" if is_list else "paragraph"
                                )
                            )
                    else:
                        # Detect lists
                        is_list = any(line.strip().startswith(("-", "*", "•")) for line in block_text_lines)
                        sections.append(
                            ExtractedSection(
                                page_number=page_num,
                                heading=current_heading,
                                content=full_block_text,
                                section_type="list" if is_list else "paragraph"
                            )
                        )

        doc.close()

        if total_extracted_chars < 50:
            raise ValueError(
                "No extractable text was found in the PDF. The document may be scanned, image-only, or empty."
            )

        log_event(
            "PDF EXTRACTION",
            f"Successfully parsed {document_name}: {total_pages} pages, {len(sections)} sections, {total_extracted_chars} characters"
        )
        return ExtractedPDFDocument(
            document_id=document_id,
            document_name=document_name,
            total_pages=total_pages,
            sections=sections
        )

pdf_parser = PyMuPDFParser()
