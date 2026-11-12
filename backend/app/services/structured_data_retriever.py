from abc import ABC, abstractmethod
from collections import OrderedDict
import os
import re
import threading
import time
from typing import List, Dict, Any, Optional, Tuple
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
    Thread-safe, cached structured data retriever supporting multi-condition
    numerical, relational, range, categorical, and aggregate query evaluation.
    """

    PREFERRED_NUMERIC_COLS = ("marks", "score", "grade", "total", "amount", "price", "salary", "age")
    AGGREGATE_PATTERN = re.compile(
        r'\b(average|mean|total|count|sum|highest|lowest|min|max|minimum|maximum|statistics|top\s+\d+)\b'
    )

    def __init__(self, max_cached_tables: int = 64):
        self.max_cached_tables = max(1, max_cached_tables)
        self._lock = threading.RLock()
        self._df_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()

        # Telemetry metrics
        self._cache_hits = 0
        self._cache_misses = 0
        self._total_queries = 0
        self._total_query_ms = 0.0

    def invalidate_cache(self, document_id: Optional[str] = None) -> None:
        with self._lock:
            if document_id is None:
                self._df_cache.clear()
            else:
                self._df_cache.pop(document_id, None)

    def _get_dataframe(self, document_id: str) -> Optional[Tuple[pd.DataFrame, List[str], List[str]]]:
        csv_path = os.path.join(settings.processed_dir, f"{document_id}.csv")
        if not os.path.exists(csv_path):
            with self._lock:
                self._df_cache.pop(document_id, None)
            return None

        try:
            stat = os.stat(csv_path)
            mtime = stat.st_mtime
            size = stat.st_size
        except OSError:
            return None

        with self._lock:
            entry = self._df_cache.get(document_id)
            if entry and entry["mtime"] == mtime and entry["size"] == size:
                self._df_cache.move_to_end(document_id)
                self._cache_hits += 1
                return entry["df"], entry["numeric_cols"], entry["non_numeric_cols"]
            self._cache_misses += 1

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            log_event("ERROR", f"Failed to load processed CSV {csv_path}: {str(e)}")
            return None

        numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        non_numeric_cols = [c for c in df.columns if c not in numeric_cols]

        with self._lock:
            self._df_cache[document_id] = {
                "mtime": mtime,
                "size": size,
                "df": df,
                "numeric_cols": numeric_cols,
                "non_numeric_cols": non_numeric_cols,
            }
            self._df_cache.move_to_end(document_id)
            while len(self._df_cache) > self.max_cached_tables:
                self._df_cache.popitem(last=False)

        return df, numeric_cols, non_numeric_cols

    def retrieve(
        self,
        query: str,
        document_id: str,
        file_name: str,
        top_k: int = 5
    ) -> List[RetrievedChunk]:
        if top_k <= 0:
            return []

        start = time.perf_counter()
        loaded = self._get_dataframe(document_id)
        if not loaded:
            return []

        df, numeric_cols, non_numeric_cols = loaded
        if df.empty:
            return []

        filtered_df = self._apply_heuristics(df, numeric_cols, non_numeric_cols, query, file_name)
        if filtered_df is None or filtered_df.empty:
            with self._lock:
                self._total_queries += 1
                self._total_query_ms += (time.perf_counter() - start) * 1000
            return []

        results: List[RetrievedChunk] = []
        query_lower = query.lower()

        # If aggregate request detected, compute and prepend summary statistics
        has_aggregate = bool(self.AGGREGATE_PATTERN.search(query_lower))
        if has_aggregate and numeric_cols:
            agg_lines = [
                f"File: {file_name} | Computed Statistics for Query",
                f"Total Matching Records: {len(filtered_df)}"
            ]
            for c in numeric_cols[:4]:
                col_name = c.replace("_", " ").title()
                mean_val = round(float(filtered_df[c].mean()), 2)
                min_val = round(float(filtered_df[c].min()), 2)
                max_val = round(float(filtered_df[c].max()), 2)
                sum_val = round(float(filtered_df[c].sum()), 2)
                agg_lines.append(
                    f"{col_name} — Average: {mean_val}, Min: {min_val}, Max: {max_val}, Total Sum: {sum_val}"
                )

            agg_text = "\n".join(agg_lines)
            results.append(
                RetrievedChunk(
                    id=f"{document_id}_computed_aggregates",
                    text=agg_text,
                    metadata={
                        "source_type": "csv",
                        "document_id": document_id,
                        "document_name": file_name,
                        "chunk_id": f"{document_id}_computed_aggregates",
                        "row_number": 1,
                        "retrieval_method": "structured_pandas"
                    },
                    score=0.99,
                    rank=1
                )
            )

        row_limit = max(1, top_k - len(results)) if top_k > 1 and results else top_k
        subset = filtered_df.head(row_limit)

        for idx, row in subset.iterrows():
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
                    score=0.98,
                    rank=len(results) + 1
                )
            )

        elapsed_ms = (time.perf_counter() - start) * 1000
        with self._lock:
            self._total_queries += 1
            self._total_query_ms += elapsed_ms

        log_event(
            "RETRIEVAL",
            f"StructuredDataRetriever matched {len(results)} chunks for query '{query}' in {file_name}"
        )
        return results

    @classmethod
    def _resolve_target_column(
        cls,
        query_lower: str,
        match_start: int,
        numeric_cols: List[str]
    ) -> Optional[str]:
        if not numeric_cols:
            return None

        # 1. Prefer numeric column mentioned in the local preceding context window
        prefix = query_lower[max(0, match_start - 40) : match_start]
        best_col = None
        best_pos = -1
        for col in numeric_cols:
            for variant in (col.lower(), col.lower().replace("_", " ")):
                pos = prefix.rfind(variant)
                if pos > best_pos:
                    best_pos = pos
                    best_col = col
        if best_col:
            return best_col

        # 2. Check anywhere in query
        for col in numeric_cols:
            if col.lower() in query_lower or col.lower().replace("_", " ") in query_lower:
                return col

        # 3. Preferred metric columns fallback
        for preferred in cls.PREFERRED_NUMERIC_COLS:
            if preferred in numeric_cols:
                return preferred
        return numeric_cols[0]

    @staticmethod
    def _overlaps(span: Tuple[int, int], used_spans: List[Tuple[int, int]]) -> bool:
        s, e = span
        return any(not (e <= us or s >= ue) for us, ue in used_spans)

    def _apply_heuristics(
        self,
        df: pd.DataFrame,
        numeric_cols: List[str],
        non_numeric_cols: List[str],
        query: str,
        file_name: str
    ) -> Optional[pd.DataFrame]:
        query_lower = query.lower()
        mask = pd.Series(True, index=df.index)
        conditions_found = False
        used_spans: List[Tuple[int, int]] = []

        # 1. Range condition: "between X and Y"
        for match in re.finditer(r'\bbetween\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)\b', query_lower):
            span = match.span()
            if self._overlaps(span, used_spans):
                continue
            used_spans.append(span)
            low = float(match.group(1))
            high = float(match.group(2))
            if low > high:
                low, high = high, low
            target_col = self._resolve_target_column(query_lower, span[0], numeric_cols)
            if target_col:
                mask = mask & (df[target_col] >= low) & (df[target_col] <= high)
                conditions_found = True

        # 2. Ordered relational patterns (longest/composite operators first to prevent >= matching =)
        num_patterns = [
            (r'(?:>=|greater than or equal to|more than or equal to|at least|minimum of|no less than)\s*(\d+(?:\.\d+)?)', '>='),
            (r'(?:<=|less than or equal to|at most|no more than)\s*(\d+(?:\.\d+)?)', '<='),
            (r'(?:!=|<>|not equal to)\s*(\d+(?:\.\d+)?)', '!='),
            (r'(?:>|above|greater than|more than|over|exceeding)\s*(\d+(?:\.\d+)?)', '>'),
            (r'(?:<|below|less than|under)\s*(\d+(?:\.\d+)?)', '<'),
            (r'(?:==|(?<![<>!=])=(?!=)|equal to|equals|scored|score of|scoring|got|marks of)\s*(\d+(?:\.\d+)?)', '=='),
        ]

        for pattern, op in num_patterns:
            for match in re.finditer(pattern, query_lower):
                span = match.span()
                if self._overlaps(span, used_spans):
                    continue
                used_spans.append(span)
                threshold = float(match.group(1))
                target_col = self._resolve_target_column(query_lower, span[0], numeric_cols)
                if target_col:
                    if op == '>=':
                        mask = mask & (df[target_col] >= threshold)
                    elif op == '<=':
                        mask = mask & (df[target_col] <= threshold)
                    elif op == '!=':
                        mask = mask & (df[target_col] != threshold)
                    elif op == '>':
                        mask = mask & (df[target_col] > threshold)
                    elif op == '<':
                        mask = mask & (df[target_col] < threshold)
                    elif op == '==':
                        mask = mask & (df[target_col] == threshold)
                    conditions_found = True

        # 3. Categorical value matching (OR within the same column, AND across distinct columns)
        for col in non_numeric_cols:
            col_series = df[col].dropna().astype(str)
            uniques = col_series.unique()
            matched_vals_lower = []
            for val in uniques:
                val_str = str(val).strip()
                if len(val_str) >= 2:
                    pattern = r'\b' + re.escape(val_str.lower()) + r'\b'
                    if re.search(pattern, query_lower):
                        matched_vals_lower.append(val_str.lower())
            if matched_vals_lower:
                mask = mask & df[col].astype(str).str.strip().str.lower().isin(matched_vals_lower)
                conditions_found = True

        # 4. Aggregate/top-N fallback when query asks for stats/top-N over whole table
        if not conditions_found and self.AGGREGATE_PATTERN.search(query_lower):
            base_name = os.path.splitext(file_name.lower())[0]
            col_mentioned = any(
                c.lower() in query_lower or c.lower().replace("_", " ") in query_lower
                for c in df.columns
            )
            dataset_signal = bool(re.search(r'\b(dataset|csv|table|records|rows|students)\b', query_lower))
            if base_name in query_lower or col_mentioned or dataset_signal:
                conditions_found = True

        if conditions_found:
            filtered = df[mask]
            if numeric_cols and not filtered.empty:
                sort_col = numeric_cols[0]
                for preferred in ("marks", "score", "total"):
                    if preferred in numeric_cols:
                        sort_col = preferred
                        break
                is_ascending = bool(re.search(r'\b(lowest|minimum|min|least|bottom|worst)\b', query_lower))
                filtered = filtered.sort_values(by=sort_col, ascending=is_ascending)
            return filtered

        return None

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            lookups = self._cache_hits + self._cache_misses
            hit_rate = round(self._cache_hits / lookups, 4) if lookups > 0 else 0.0
            avg_ms = round(self._total_query_ms / self._total_queries, 3) if self._total_queries > 0 else 0.0
            return {
                "cached_tables_count": len(self._df_cache),
                "max_cached_tables": self.max_cached_tables,
                "cached_document_ids": list(self._df_cache.keys()),
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "cache_hit_rate": hit_rate,
                "total_queries": self._total_queries,
                "avg_query_ms": avg_ms,
            }


structured_retriever = PandasStructuredDataRetriever()
