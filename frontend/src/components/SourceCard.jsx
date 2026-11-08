import React, { useState } from 'react';
import { FileText, Table, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';

export default function SourceCard({ source }) {
  const [expanded, setExpanded] = useState(false);
  const isPdf = source.source_type === 'pdf';
  const isSchema = source.source_type === 'csv_schema';

  return (
    <div
      style={{
        background: 'rgba(255, 255, 255, 0.03)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-md)',
        padding: '8px 12px',
        fontSize: '12px',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
      }}
      onClick={() => setExpanded(!expanded)}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--border-hover)')}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
          {isPdf ? (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '2px 6px',
                borderRadius: '4px',
                background: 'rgba(244, 63, 94, 0.15)',
                color: '#fb7185',
                fontWeight: 600,
              }}
            >
              <FileText size={12} /> PDF
            </span>
          ) : isSchema ? (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '2px 6px',
                borderRadius: '4px',
                background: 'rgba(245, 158, 11, 0.15)',
                color: '#fbbf24',
                fontWeight: 600,
              }}
            >
              <Table size={12} /> Schema
            </span>
          ) : (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '2px 6px',
                borderRadius: '4px',
                background: 'rgba(16, 185, 129, 0.15)',
                color: '#34d399',
                fontWeight: 600,
              }}
            >
              <Table size={12} /> CSV
            </span>
          )}

          <span
            style={{
              fontWeight: 500,
              color: 'var(--text-primary)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: '160px',
            }}
          >
            {source.file_name}
          </span>

          {isPdf && source.page && (
            <span style={{ color: 'var(--text-muted)' }}>• Page {source.page}</span>
          )}

          {!isPdf && source.row && (
            <span style={{ color: 'var(--text-muted)' }}>• Row {source.row}</span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          {source.score !== undefined && source.score !== null && (
            <span
              style={{
                padding: '1px 5px',
                borderRadius: '4px',
                background: 'rgba(139, 92, 246, 0.12)',
                color: 'var(--text-accent)',
                fontFamily: 'var(--font-mono)',
                fontSize: '10px',
              }}
            >
              {(source.score * 100).toFixed(0)}% match
            </span>
          )}
          {expanded ? <ChevronUp size={14} color="#94a3b8" /> : <ChevronDown size={14} color="#94a3b8" />}
        </div>
      </div>

      {expanded && source.snippet && (
        <div
          style={{
            marginTop: '8px',
            paddingTop: '8px',
            borderTop: '1px solid rgba(255, 255, 255, 0.05)',
            color: 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)',
            fontSize: '11px',
            lineHeight: '1.4',
            whiteSpace: 'pre-wrap',
            maxHeight: '180px',
            overflowY: 'auto',
          }}
        >
          {source.snippet}
        </div>
      )}
    </div>
  );
}
