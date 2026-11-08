import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Bot,
  User,
  Sparkles,
  RotateCcw,
  Layers,
  ArrowRight,
  Database,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import SourceCard from './SourceCard';

export default function ChatArea({
  messages,
  onSendMessage,
  loading,
  onClearChat,
  onOpenVisualizer,
  activeFilter,
  hasTrace,
  llmProvider,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!input.trim() || loading) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const samplePrompts = [
    { text: 'Explain 2NF and 3NF database normalization', icon: '📄' },
    { text: 'Which students scored above 90 in DBMS?', icon: '📊' },
    { text: 'Based on the DBMS normalization section and students dataset, which students scored highest?', icon: '⚡' },
    { text: 'What columns and details are in the students dataset?', icon: '📋' },
  ];

  return (
    <div
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        backgroundColor: 'var(--bg-primary)',
        position: 'relative',
      }}
    >
      {/* Top Action Bar */}
      <header
        style={{
          padding: '14px 28px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'var(--bg-glass)',
          backdropFilter: 'blur(12px)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
            Retrieval-Augmented Assistant
          </span>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)',
              background: 'rgba(139, 92, 246, 0.15)',
              color: 'var(--text-accent)',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            Scope: {activeFilter.toUpperCase()}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={onOpenVisualizer}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '7px 12px',
              borderRadius: 'var(--radius-md)',
              background: hasTrace ? 'rgba(139, 92, 246, 0.2)' : 'rgba(255, 255, 255, 0.05)',
              border: `1px solid ${hasTrace ? 'var(--accent-purple)' : 'var(--border-subtle)'}`,
              color: hasTrace ? 'var(--text-accent)' : 'var(--text-secondary)',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            <Layers size={14} />
            Pipeline Visualizer
            {hasTrace && (
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  background: 'var(--accent-purple)',
                }}
              />
            )}
          </button>

          <button
            onClick={onClearChat}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '7px 12px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-secondary)',
              fontSize: '12px',
              fontWeight: 500,
            }}
            title="Clear conversation messages"
          >
            <RotateCcw size={14} />
            Clear
          </button>
        </div>
      </header>

      {/* Messages Feed */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '24px 28px',
          display: 'flex',
          flexDirection: 'column',
          gap: '20px',
        }}
      >
        {messages.length === 0 ? (
          <div
            style={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              maxWidth: '680px',
              margin: '0 auto',
              textAlign: 'center',
              padding: '40px 20px',
            }}
          >
            <div
              style={{
                width: '56px',
                height: '56px',
                borderRadius: '16px',
                background: 'var(--grad-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: 'var(--shadow-glow)',
                marginBottom: '16px',
              }}
            >
              <Sparkles size={28} color="#fff" />
            </div>
            <h2 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px' }}>
              Multi-Modal RAG Knowledge Assistant
            </h2>
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '28px', lineHeight: '1.6' }}>
              Query simultaneously across PDF documents (headings, pages, text) and structured CSV datasets
              (schema detection, row records, numerical filters) powered by OpenAI API.
            </p>


            <div
              style={{
                width: '100%',
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '10px',
                textAlign: 'left',
              }}
            >
              {samplePrompts.map((p, idx) => (
                <div
                  key={idx}
                  onClick={() => onSendMessage(p.text)}
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '12px 14px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-accent)';
                    e.currentTarget.style.transform = 'translateY(-1px)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-subtle)';
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  <span style={{ fontSize: '18px' }}>{p.icon}</span>
                  <span style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 500 }}>
                    {p.text}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => {
            const isUser = msg.role === 'user';
            return (
              <div
                key={idx}
                className="fade-in"
                style={{
                  display: 'flex',
                  gap: '14px',
                  alignSelf: isUser ? 'flex-end' : 'flex-start',
                  maxWidth: isUser ? '75%' : '85%',
                }}
              >
                {!isUser && (
                  <div
                    style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '8px',
                      background: 'var(--grad-primary)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <Bot size={18} color="#fff" />
                  </div>
                )}

                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                    alignItems: isUser ? 'flex-end' : 'flex-start',
                  }}
                >
                  <div
                    style={{
                      background: isUser ? 'var(--accent-purple)' : 'var(--bg-card)',
                      border: isUser ? 'none' : '1px solid var(--border-subtle)',
                      borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                      padding: '14px 18px',
                      color: '#f8fafc',
                      fontSize: '14px',
                      lineHeight: '1.6',
                      boxShadow: 'var(--shadow-sm)',
                      whiteSpace: 'pre-wrap',
                      fontFamily: 'var(--font-sans)',
                    }}
                  >
                    {msg.content}
                  </div>

                  {/* Sources citation section */}
                  {!isUser && msg.sources && msg.sources.length > 0 && (
                    <div style={{ marginTop: '4px', width: '100%' }}>
                      <div
                        style={{
                          fontSize: '11px',
                          color: 'var(--text-muted)',
                          fontWeight: 600,
                          marginBottom: '6px',
                          textTransform: 'uppercase',
                          letterSpacing: '0.05em',
                        }}
                      >
                        Retrieved Sources ({msg.sources.length})
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {msg.sources.map((src, sIdx) => (
                          <SourceCard key={sIdx} source={src} />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Metadata latency badge */}
                  {!isUser && msg.metadata && (
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', gap: '8px' }}>
                      <span>Latency: {msg.metadata.latency_ms || 0}ms</span>
                      <span>•</span>
                      <span>Chunks: {msg.metadata.retrieval_count || 0}</span>
                    </div>
                  )}
                </div>

                {isUser && (
                  <div
                    style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '8px',
                      background: 'rgba(255, 255, 255, 0.1)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <User size={18} color="#fff" />
                  </div>
                )}
              </div>
            );
          })
        )}

        {loading && (
          <div
            className="fade-in"
            style={{
              display: 'flex',
              gap: '14px',
              alignSelf: 'flex-start',
              maxWidth: '80%',
            }}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'var(--grad-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Bot size={18} color="#fff" />
            </div>
            <div
              style={{
                background: 'var(--bg-card)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '16px 16px 16px 4px',
                padding: '14px 20px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
              }}
            >
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: 'var(--accent-purple)',
                  animation: 'pulseGlow 1.2s infinite ease-in-out',
                }}
              />
              <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                Retrieving chunks and reasoning with {llmProvider === 'claude' ? 'Claude' : 'OpenAI'}...
              </span>

            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Bottom Input Box */}
      <div
        style={{
          padding: '18px 28px',
          borderTop: '1px solid var(--border-subtle)',
          background: 'var(--bg-glass)',
          backdropFilter: 'blur(12px)',
        }}
      >
        <form
          onSubmit={handleSubmit}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            background: 'rgba(255, 255, 255, 0.04)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius-lg)',
            padding: '8px 12px 8px 18px',
            boxShadow: 'var(--shadow-sm)',
            transition: 'border-color 0.2s ease',
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent-purple)')}
          onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question across your PDF documents and CSV datasets..."
            disabled={loading}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--text-primary)',
              fontSize: '14px',
              fontFamily: 'inherit',
            }}
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            style={{
              width: '38px',
              height: '38px',
              borderRadius: '10px',
              background: input.trim() && !loading ? 'var(--grad-primary)' : 'rgba(255, 255, 255, 0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              boxShadow: input.trim() && !loading ? 'var(--shadow-glow)' : 'none',
              cursor: input.trim() && !loading ? 'pointer' : 'default',
            }}
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
}
