import os
import re
from typing import List, Dict, Any, Tuple
import pandas as pd
from app.core.config import settings
from app.core.logging import log_event
from app.models.chunk import Chunk, ChunkMetadata

class ProcessedCSV:
    def __init__(
        self,
        document_id: str,
        file_name: str,
        df: pd.DataFrame,
        schema_text: str,
        schema_chunk: Chunk,
        record_chunks: List[Chunk],
        column_types: Dict[str, str],
        row_count: int
    ):
        self.document_id = document_id
        self.file_name = file_name
        self.df = df
        self.schema_text = schema_text
        self.schema_chunk = schema_chunk
        self.record_chunks = record_chunks
        self.column_types = column_types
        self.row_count = row_count

class CSVService:
    def normalize_column_name(self, col: str) -> str:
        """Normalize column name to lowercase, alphanumeric with underscores."""
        col = str(col).strip()
        col = re.sub(r'[\s\.\-\/\\]+', '_', col)
        col = re.sub(r'[^\w]', '', col)
        return col.lower() or "unnamed_column"

    def detect_type(self, series: pd.Series) -> str:
        """Map pandas dtype to human-readable type."""
        dtype = str(series.dtype).lower()
        if "int" in dtype:
            return "integer"
        elif "float" in dtype:
            return "decimal/float"
        elif "bool" in dtype:
            return "boolean"
        elif "datetime" in dtype:
            return "datetime"
        else:
            return "string/text"

    def parse_csv(self, file_path: str, document_id: str, file_name: str) -> ProcessedCSV:
        log_event("CSV PROCESSING", f"Parsing CSV: {file_name} from {file_path}")
        
        # 1. Read file with fallback encodings
        encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252"]
        df = None
        for enc in encodings:
            try:
                df = pd.read_csv(file_path, encoding=enc)
                break
            except Exception:
                continue

        if df is None:
            raise ValueError(f"Failed to read CSV '{file_name}'. Ensure it is a valid delimited text file.")

        if df.empty or len(df.columns) == 0:
            raise ValueError(f"The CSV file '{file_name}' is empty.")

        row_count = len(df)
        log_event("CSV PROCESSING", f"Loaded {row_count} rows and {len(df.columns)} columns")

        # 2. Normalize columns
        original_cols = list(df.columns)
        normalized_cols = [self.normalize_column_name(c) for c in original_cols]
        # Handle duplicates if any
        seen = {}
        deduped_cols = []
        for col in normalized_cols:
            if col in seen:
                seen[col] += 1
                deduped_cols.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                deduped_cols.append(col)
        df.columns = deduped_cols

        # 3. Detect column data types & summary
        column_types = {}
        missing_values_summary = {}
        for col in df.columns:
            column_types[col] = self.detect_type(df[col])
            missing_count = int(df[col].isna().sum())
            if missing_count > 0:
                missing_values_summary[col] = missing_count

        # 4. Generate Schema Representation
        schema_lines = [
            f"Dataset: {file_name}",
            f"Total Rows: {row_count}",
            f"Total Columns: {len(df.columns)}",
            "",
            "Columns:"
        ]
        for col in df.columns:
            type_desc = column_types[col]
            # Sample unique values for categorical or string fields
            unique_samples = df[col].dropna().unique()[:3]
            sample_str = ""
            if len(unique_samples) > 0:
                sample_str = f" (Sample values: {', '.join(str(s) for s in unique_samples)})"
            schema_lines.append(f"- {col}: {type_desc}{sample_str}")

        if missing_values_summary:
            schema_lines.append("\nMissing Values:")
            for col, count in missing_values_summary.items():
                schema_lines.append(f"- {col}: {count} missing values")

        schema_text = "\n".join(schema_lines)

        schema_chunk_id = f"{document_id}_schema"
        schema_chunk = Chunk(
            id=schema_chunk_id,
            text=schema_text,
            metadata=ChunkMetadata(
                source_type="csv_schema",
                document_id=document_id,
                document_name=file_name,
                chunk_id=schema_chunk_id,
                columns=list(df.columns),
                additional_meta={"total_rows": row_count}
            )
        )

        # 5. Convert each row into meaningful textual representation
        record_chunks: List[Chunk] = []
        for idx, row in df.iterrows():
            row_num = int(idx) + 1
            row_lines = [f"File: {file_name} | Row {row_num}"]
            row_dict = {}
            for col in df.columns:
                val = row[col]
                display_val = "N/A" if pd.isna(val) else str(val)
                row_lines.append(f"{col.replace('_', ' ').title()}: {display_val}")
                row_dict[col] = None if pd.isna(val) else val

            row_text = "\n".join(row_lines)
            chunk_id = f"{document_id}_row_{row_num}"
            
            # Store scalar column values in metadata for structured filtering
            additional_meta = {"row_number": row_num}
            for col in df.columns[:10]:  # Up to 10 key columns for metadata filtering
                val = row_dict[col]
                if isinstance(val, (int, float, str, bool)):
                    additional_meta[f"col_{col}"] = val

            record_chunks.append(
                Chunk(
                    id=chunk_id,
                    text=row_text,
                    metadata=ChunkMetadata(
                        source_type="csv",
                        document_id=document_id,
                        document_name=file_name,
                        chunk_id=chunk_id,
                        row_number=row_num,
                        columns=list(df.columns),
                        additional_meta=additional_meta
                    )
                )
            )

        # 6. Save cleaned dataframe to processed folder for structured query engine
        processed_path = os.path.join(settings.processed_dir, f"{document_id}.csv")
        df.to_csv(processed_path, index=False)

        log_event(
            "CSV PROCESSING",
            f"Successfully processed {file_name}: {len(record_chunks)} record chunks created and stored"
        )

        return ProcessedCSV(
            document_id=document_id,
            file_name=file_name,
            df=df,
            schema_text=schema_text,
            schema_chunk=schema_chunk,
            record_chunks=record_chunks,
            column_types=column_types,
            row_count=row_count
        )

csv_service = CSVService()
