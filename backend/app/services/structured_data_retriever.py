import os
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd
from app.core.config import settings
from app.core.logging import log_event
from app.models.query import RetrievedChunk

class BaseStructuredDataRetriever(ABC):
    @abstractmethod
    def retrieve(
        self,
        query: str,
        document_id: str,
        file_name: str,
        top_k: int = 5
    ) -> List[RetrievedChunk]:
        pass

class PandasStructuredDataRetriever(BaseStructuredDataRetriever):
    """
    Structured data retriever supporting condition parsing and dataframe filtering.
    Enables accurate retrieval for numerical and categorical queries (e.g., 'marks > 90', 'DBMS').
    """
    def retrieve(
        self,
        query: str,
        document_id: str,
        file_name: str,
        top_k: int = 5
    ) -> List[RetrievedChunk]:
        csv_path = os.path.join(settings.processed_dir, f"{document_id}.csv")
        if not os.path.exists(csv_path):
            return []

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            log_event("ERROR", f"Failed to load processed CSV {csv_path}: {str(e)}")
            return []

        if df.empty:
            return []

        filtered_df = self._apply_heuristics(df, query)
        if filtered_df is None or filtered_df.empty:
            return []

        # Convert top results to RetrievedChunk
        results: List[RetrievedChunk] = []
        subset = filtered_df.head(top_k)

        for rank, (idx, row) in enumerate(subset.iterrows(), start=1):
            row_num = int(idx) + 1
            row_lines = [f"File: {file_name} | Row {row_num}"]
            for col in df.columns:
                val = row[col]
                display_val = "N/A" if pd.isna(val) else str(val)
                row_lines.append(f"{col.replace('_', ' ').title()}: {display_val}")

            text = "\n".join(row_lines)
            chunk_id = f"{document_id}_row_{row_num}"
            results.append(
                RetrievedChunk(
                    id=chunk_id,
                    text=text,
                    metadata={
                        "source_type": "csv",
                        "document_id": document_id,
                        "document_name": file_name,
                        "chunk_id": chunk_id,
                        "row_number": row_num,
                        "retrieval_method": "structured_pandas"
                    },
                    score=0.98,  # High confidence for explicit structured filter match
                    rank=rank
                )
            )

        log_event(
            "RETRIEVAL",
            f"StructuredDataRetriever matched {len(results)} rows for query '{query}' in {file_name}"
        )
        return results

    def _apply_heuristics(self, df: pd.DataFrame, query: str) -> Optional[pd.DataFrame]:
        query_lower = query.lower()
        mask = pd.Series(True, index=df.index)
        conditions_found = False

        # 1. Check numerical conditions (e.g. > 90, above 90, greater than 90, < 50, below 50)
        num_patterns = [
            (r'(?:above|greater than|more than|>|>=)\s*(\d+(?:\.\d+)?)', '>'),
            (r'(?:below|less than|<|<=)\s*(\d+(?:\.\d+)?)', '<'),
            (r'(?:equal to|==|=|scored|score of|scoring|got|marks of)\s*(\d+(?:\.\d+)?)', '==')
        ]

        # Identify numeric columns in dataframe
        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

        for pattern, op in num_patterns:
            match = re.search(pattern, query_lower)
            if match:
                threshold = float(match.group(1))
                # Try to find relevant numeric column mentioned in query, else check all numeric columns
                target_col = None
                for col in numeric_cols:
                    if col in query_lower or col.replace('_', ' ') in query_lower:
                        target_col = col
                        break
                if not target_col and numeric_cols:
                    # Common names: marks, score, salary, price, age, count
                    for preferred in ["marks", "score", "grade", "total", "amount", "price"]:
                        if preferred in numeric_cols:
                            target_col = preferred
                            break
                    if not target_col:
                        target_col = numeric_cols[0]

                if target_col:
                    if op == '>':
                        mask = mask & (df[target_col] > threshold)
                    elif op == '<':
                        mask = mask & (df[target_col] < threshold)
                    elif op == '==':
                        mask = mask & (df[target_col] == threshold)
                    conditions_found = True

        # 2. Check categorical value matching (e.g. subject == "DBMS")
        for col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                # Check if any unique value of this column appears as an isolated word in query
                uniques = df[col].dropna().astype(str).unique()
                for val in uniques:
                    val_str = str(val).strip()
                    if len(val_str) >= 2:
                        pattern = r'\b' + re.escape(val_str.lower()) + r'\b'
                        if re.search(pattern, query_lower):
                            mask = mask & (df[col].astype(str).str.lower() == val_str.lower())
                            conditions_found = True

        if conditions_found:
            filtered = df[mask]
            # If multiple rows match, sort by numeric column if available (descending)
            if numeric_cols and not filtered.empty:
                sort_col = numeric_cols[0]
                for preferred in ["marks", "score", "total"]:
                    if preferred in numeric_cols:
                        sort_col = preferred
                        break
                filtered = filtered.sort_values(by=sort_col, ascending=False)
            return filtered

        return None

structured_retriever = PandasStructuredDataRetriever()
