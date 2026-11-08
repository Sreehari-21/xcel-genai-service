import React, { useState } from 'react';
import { X, Layers, Cpu, Database, CheckCircle2, ChevronRight, Activity, Terminal } from 'lucide-react';

export default function PipelineVisualizer({ isOpen, onClose, trace, lastQuery, lastResponse }) {
  const [activeTab, setActiveTab] = useState('overview');

  if (!isOpen) return null;

  const analysis = trace?.analysis || {};
  const candidates = trace?.retrieved_candidates || [];

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(8px)',
        zIndex: 1000,
        display: 'flex',
        justifyContent: 'flex-end',
        animation: 'fadeIn 0.2s ease-out',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 'min(900px, 92vw)',
          height: '100%',
          backgroundColor: 'var(--bg-secondary)',
          borderLeft: '1px solid var(--border-hover)',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'linear-gradient(180deg, rgba(139, 92, 246, 0.08) 0%, transparent 100%)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '34px',
                height: '34px',
                borderRadius: '8px',
                background: 'var(--grad-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: 'var(--shadow-glow)',
              }}
            >
              <Layers size={18} color="#fff" />
            </div>
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)' }}>
                RAG Pipeline Inspector
              </h2>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Live Execution Trace & Multi-Modal Diagnostics
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '6px',
              color: 'var(--text-secondary)',
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div
          style={{
            display: 'flex',
            gap: '8px',
            padding: '12px 24px',
            borderBottom: '1px solid var(--border-subtle)',
            background: 'var(--bg-tertiary)',
          }}
        >
          {[
            { id: 'overview', label: 'Pipeline Graph', icon: Activity },
            { id: 'candidates', label: `Retrieved Chunks (${candidates.length})`, icon: Database },
            { id: 'context', label: 'Constructed Context', icon: Terminal },
            { id: 'metrics', label: 'Execution Metrics', icon: Cpu },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 14px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '13px',
                  fontWeight: 500,
                  background: isActive ? 'rgba(139, 92, 246, 0.2)' : 'transparent',
                  color: isActive ? 'var(--text-accent)' : 'var(--text-secondary)',
                  border: isActive ? '1px solid var(--accent-purple)' : '1px solid transparent',
                }}
              >
                <Icon size={14} />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
          {activeTab === 'overview' && (
            <div>
              <div
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '16px',
                  marginBottom: '24px',
                }}
              >
                <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, marginBottom: '6px' }}>
                  Target Query
                </div>
                <div style={{ fontSize: '15px', color: 'var(--text-primary)', fontWeight: 500, fontFamily: 'var(--font-sans)' }}>
                  "{lastQuery || 'No query executed yet'}"
                </div>
              </div>

              {/* Visual Pipeline Stages */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {/* Stage 1: Preprocessing & Query Analysis */}
                <div
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '16px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <CheckCircle2 size={16} color="#10b981" />
                      <span style={{ fontWeight: 600, fontSize: '14px' }}>Stage 1 — Query Analysis & Intent Detection</span>
                    </div>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: '12px',
                        background: 'rgba(139, 92, 246, 0.2)',
                        color: 'var(--text-accent)',
                        fontSize: '11px',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                      }}
                    >
                      {analysis.query_type || 'MIXED'}
                    </span>
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                    Numerical Filter Detected: <strong>{analysis.has_numerical_filter ? 'Yes' : 'No'}</strong>
                    {analysis.detected_keywords?.length > 0 && (
                      <span style={{ marginLeft: '12px' }}>
                        Keywords: <em>{analysis.detected_keywords.join(', ')}</em>
                      </span>
                    )}
                  </div>
                </div>

                {/* Stage 2: Parallel Multi-Modal Retrieval */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: '12px',
                  }}
                >
                  <div
                    style={{
                      background: 'rgba(244, 63, 94, 0.05)',
                      border: '1px solid rgba(244, 63, 94, 0.2)',
                      borderRadius: 'var(--radius-md)',
                      padding: '14px',
                    }}
                  >
                    <div style={{ fontWeight: 600, color: '#fb7185', fontSize: '13px', marginBottom: '6px' }}>
                      PDF Vector Index
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      Retrieved: <strong>{trace?.pdf_candidates_count || 0} chunks</strong>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Collection: pdf_documents
                    </div>
                  </div>

                  <div
                    style={{
                      background: 'rgba(16, 185, 129, 0.05)',
                      border: '1px solid rgba(16, 185, 129, 0.2)',
                      borderRadius: 'var(--radius-md)',
                      padding: '14px',
                    }}
                  >
                    <div style={{ fontWeight: 600, color: '#34d399', fontSize: '13px', marginBottom: '6px' }}>
                      CSV Records & Schema Index
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      Retrieved: <strong>{trace?.csv_candidates_count || 0} rows</strong> (Vectors) +{' '}
                      <strong>{trace?.structured_candidates_count || 0} rows</strong> (Structured Pandas)
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Collections: csv_records, csv_schemas
                    </div>
                  </div>
                </div>

                {/* Stage 3: Re-ranking & Merging */}
                <div
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '16px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                    <CheckCircle2 size={16} color="#10b981" />
                    <span style={{ fontWeight: 600, fontSize: '14px' }}>Stage 3 — Re-ranking & Deduplication</span>
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                    Weighted rank score applied with lexical overlap, query density, and structured filter boosting.
                    Selected Top <strong>{candidates.length}</strong> candidates for {trace?.llm_provider ? trace.llm_provider.toUpperCase() : 'LLM'}.
                  </div>
                </div>

                {/* Stage 4: OpenAI / LLM Synthesis */}
                <div
                  style={{
                    background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.1) 0%, rgba(99, 102, 241, 0.05) 100%)',
                    border: '1px solid var(--border-accent)',
                    borderRadius: 'var(--radius-md)',
                    padding: '16px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <CheckCircle2 size={16} color="#10b981" />
                      <span style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-accent)' }}>
                        Stage 4 — {trace?.llm_provider ? trace.llm_provider.toUpperCase() : 'LLM'} Synthesis
                      </span>
                    </div>
                    <span style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                      {trace?.llm_model || 'gpt-4o'}
                    </span>
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                    Tokens: Input {trace?.tokens_usage?.input_tokens || 0} | Output{' '}
                    {trace?.tokens_usage?.output_tokens || 0} • Latency {trace?.total_latency_ms || 0}ms
                  </div>
                </div>
              </div>
            </div>
          )}


          {activeTab === 'candidates' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {candidates.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px' }}>
                  No retrieved candidates available. Run a query first.
                </div>
              ) : (
                candidates.map((cand, idx) => (
                  <div
                    key={cand.id || idx}
                    style={{
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-md)',
                      padding: '14px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span
                          style={{
                            width: '22px',
                            height: '22px',
                            borderRadius: '50%',
                            background: 'rgba(255, 255, 255, 0.1)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '11px',
                            fontWeight: 600,
                          }}
                        >
                          {idx + 1}
                        </span>
                        <span style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
                          {cand.document}
                        </span>
                        {cand.page && (
                          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Page {cand.page}</span>
                        )}
                        {cand.row && (
                          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Row {cand.row}</span>
                        )}
                      </div>
                      <span
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '11px',
                          color: 'var(--text-accent)',
                          padding: '2px 8px',
                          background: 'rgba(139, 92, 246, 0.15)',
                          borderRadius: '4px',
                        }}
                      >
                        Score: {cand.score}
                      </span>
                    </div>
                    <div
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '12px',
                        color: 'var(--text-secondary)',
                        background: 'rgba(0, 0, 0, 0.25)',
                        padding: '10px',
                        borderRadius: 'var(--radius-sm)',
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {cand.snippet}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'context' && (
            <div>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
                This is the exact context formatted and passed to OpenAI's system prompt for answer generation:
              </p>
              <pre
                style={{
                  background: 'rgba(0, 0, 0, 0.4)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '16px',
                  fontSize: '12px',
                  color: '#e2e8f0',
                  lineHeight: '1.6',
                  whiteSpace: 'pre-wrap',
                  maxHeight: '500px',
                  overflowY: 'auto',
                }}
              >
                {lastResponse?.retrieved_chunks?.map((c, i) => `[CHUNK ${i + 1}] (${c.metadata?.source_type}) ${c.metadata?.document_name}:\n${c.text}\n`).join('\n---\n') || 'No context generated yet.'}
              </pre>
            </div>
          )}

          {activeTab === 'metrics' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '18px',
                }}
              >
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Total Pipeline Latency
                </div>
                <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
                  {trace?.total_latency_ms || 0} ms
                </div>
              </div>

              <div
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '18px',
                }}
              >
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  LLM Model
                </div>
                <div style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-accent)', marginTop: '6px' }}>
                  {trace?.llm_model || 'gpt-4o'}
                </div>
              </div>


              <div
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '18px',
                }}
              >
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Input Tokens
                </div>
                <div style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '4px' }}>
                  {trace?.tokens_usage?.input_tokens || 0}
                </div>
              </div>

              <div
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: '18px',
                }}
              >
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Output Tokens
                </div>
                <div style={{ fontSize: '24px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '4px' }}>
                  {trace?.tokens_usage?.output_tokens || 0}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
