import re
from abc import ABC, abstractmethod
from typing import List, Optional
from app.core.config import settings
from app.core.logging import log_event
from app.models.chunk import Chunk, ChunkMetadata
from app.services.pdf_service import ExtractedPDFDocument, ExtractedSection

class BaseChunker(ABC):
    @abstractmethod
    def chunk_pdf(self, doc: ExtractedPDFDocument) -> List[Chunk]:
        pass

class StructureAwareChunker(BaseChunker):
    def __init__(self, chunk_size: int = settings.chunk_size, chunk_overlap: int = settings.chunk_overlap):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _split_text_recursively(self, text: str) -> List[str]:
        """
        Recursively split oversized text blocks:
        1. By double newline (paragraphs)
        2. By single newline
        3. By sentences (. ! ?)
        4. By spaces
        Ensures overlap between adjacent split chunks.
        """
        if len(text) <= self.chunk_size:
            return [text.strip()] if text.strip() else []

        # Split into sentence/line segments
        sentence_delimiters = r'(?<=[.?!])\s+|\n+'
        segments = [s.strip() for s in re.split(sentence_delimiters, text) if s.strip()]
        
        chunks = []
        current_chunk = []
        current_len = 0

        for seg in segments:
            seg_len = len(seg)
            if current_len + seg_len + 1 > self.chunk_size and current_chunk:
                chunk_str = " ".join(current_chunk)
                chunks.append(chunk_str)
                
                # Create overlap buffer from trailing segments
                overlap_chunk = []
                overlap_len = 0
                for prev in reversed(current_chunk):
                    if overlap_len + len(prev) <= self.chunk_overlap:
                        overlap_chunk.insert(0, prev)
                        overlap_len += len(prev) + 1
                    else:
                        break
                current_chunk = overlap_chunk
                current_len = overlap_len

            current_chunk.append(seg)
            current_len += seg_len + 1

        if current_chunk:
            final_str = " ".join(current_chunk).strip()
            if final_str:
                chunks.append(final_str)

        return chunks

    def chunk_pdf(self, doc: ExtractedPDFDocument) -> List[Chunk]:
        log_event("CHUNKING", f"Structure-aware chunking for {doc.document_name} ({len(doc.sections)} sections)")
        all_chunks: List[Chunk] = []
        chunk_idx = 1

        # Group sections by page and section/heading
        current_page = None
        current_heading = "General"
        accumulator: List[str] = []
        acc_len = 0

        def flush_accumulator():
            nonlocal chunk_idx, accumulator, acc_len, current_page, current_heading
            if not accumulator:
                return
            combined_text = "\n\n".join(accumulator).strip()
            if not combined_text:
                accumulator = []
                acc_len = 0
                return

            # Check if oversized
            if len(combined_text) > self.chunk_size:
                sub_texts = self._split_text_recursively(combined_text)
                for sub in sub_texts:
                    chunk_id = f"{doc.document_id}_chunk_{chunk_idx}"
                    all_chunks.append(
                        Chunk(
                            id=chunk_id,
                            text=sub,
                            metadata=ChunkMetadata(
                                source_type="pdf",
                                document_id=doc.document_id,
                                document_name=doc.document_name,
                                chunk_id=chunk_id,
                                page_number=current_page or 1,
                                section=current_heading
                            )
                        )
                    )
                    chunk_idx += 1
            else:
                chunk_id = f"{doc.document_id}_chunk_{chunk_idx}"
                all_chunks.append(
                    Chunk(
                        id=chunk_id,
                        text=combined_text,
                        metadata=ChunkMetadata(
                            source_type="pdf",
                            document_id=doc.document_id,
                            document_name=doc.document_name,
                            chunk_id=chunk_id,
                            page_number=current_page or 1,
                            section=current_heading
                        )
                    )
                )
                chunk_idx += 1

            accumulator = []
            acc_len = 0

        for section in doc.sections:
            # When page changes or a new major heading is encountered, flush if accumulator has enough content
            heading_changed = (section.section_type == "heading" and section.heading != current_heading)
            page_changed = (current_page is not None and section.page_number != current_page)

            if (heading_changed or page_changed) and acc_len > 250:
                flush_accumulator()

            if section.page_number:
                current_page = section.page_number
            if section.heading:
                current_heading = section.heading

            # For tables, preserve table structure as its own discrete chunk
            if section.section_type == "table":
                flush_accumulator()
                chunk_id = f"{doc.document_id}_chunk_{chunk_idx}"
                all_chunks.append(
                    Chunk(
                        id=chunk_id,
                        text=section.content,
                        metadata=ChunkMetadata(
                            source_type="pdf",
                            document_id=doc.document_id,
                            document_name=doc.document_name,
                            chunk_id=chunk_id,
                            page_number=section.page_number,
                            section=f"{current_heading} (Table)"
                        )
                    )
                )
                chunk_idx += 1
                continue

            sec_len = len(section.content)
            if acc_len + sec_len + 2 > self.chunk_size and accumulator:
                flush_accumulator()

            accumulator.append(section.content)
            acc_len += sec_len + 2

        # Final flush
        flush_accumulator()

        log_event("CHUNKING", f"Generated {len(all_chunks)} chunks for PDF {doc.document_name}")
        return all_chunks

chunking_service = StructureAwareChunker()
