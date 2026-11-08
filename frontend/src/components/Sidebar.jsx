import React, { useRef, useState } from 'react';
import {
  Upload,
  FileText,
  Table,
  Trash2,
  CheckCircle,
  AlertCircle,
  Loader2,
  Sparkles,
  Layers,
  Filter,
  FileSpreadsheet
} from 'lucide-react';
import { uploadFile, deleteDocument } from '../services/api';

export default function Sidebar({
  documents,
  onDocumentsChange,
  activeFilter,
  onFilterChange,
  health,
  onLoadSample,
}) {
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const fileInputRef = useRef(null);

  const handleFileDrop = async (e) => {
    e.preventDefault();
    if (uploading) return;
    const file = e.dataTransfer?.files?.[0];
    if (file) handleUpload(file);
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file) handleUpload(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleUpload = async (file) => {
    setErrorMsg('');
    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'pdf' && ext !== 'csv') {
      setErrorMsg('Only .pdf and .csv files are supported.');
      return;
    }

    try {
      setUploading(true);
      setUploadStatus('Uploading file...');
      await new Promise((r) => setTimeout(r, 200));

      setUploadStatus(ext === 'pdf' ? 'Extracting PDF layout & text...' : 'Parsing CSV & detecting schema...');
      await new Promise((r) => setTimeout(r, 300));

      setUploadStatus('Chunking & generating embeddings...');
      const res = await uploadFile(file, ext);

      setUploadStatus('Indexing into vector store...');
      await new Promise((r) => setTimeout(r, 200));

      setUploadStatus('Completed!');
      onDocumentsChange();
    } catch (err) {
      setErrorMsg(err.message || 'Upload failed');
    } finally {
      setTimeout(() => {
        setUploading(false);
        setUploadStatus('');
      }, 1200);
    }
  };

  const handleDelete = async (docId, e) => {
    e.stopPropagation();
    try {
      await deleteDocument(docId);
      onDocumentsChange();
    } catch (err) {
      setErrorMsg('Failed to delete document');
    }
  };

  return (
    <aside
      style={{
        width: '320px',
        backgroundColor: 'var(--bg-secondary)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        userSelect: 'none',
      }}
    >
      {/* Brand Header */}
      <div
        style={{
          padding: '20px 20px 16px 20px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'var(--grad-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: 'var(--shadow-glow)',
              }}
            >
              <Sparkles size={18} color="#fff" />
            </div>
            <div>
              <h1 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
                XCEL RAG
              </h1>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>PDF + CSV Knowledge Core</span>
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '3px 8px',
              borderRadius: 'var(--radius-full)',
              background: health?.status === 'healthy' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
              border: `1px solid ${health?.status === 'healthy' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
            }}
          >
            <div
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: health?.status === 'healthy' ? '#10b981' : '#f43f5e',
              }}
            />
            <span style={{ fontSize: '10px', fontWeight: 600, color: health?.status === 'healthy' ? '#34d399' : '#fb7185' }}>
              ONLINE
            </span>
          </div>
        </div>

        {/* Source Filter Switcher */}
        <div style={{ marginTop: '6px' }}>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
            <Filter size={12} /> RETRIEVAL SCOPE
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr',
              gap: '4px',
              background: 'rgba(0, 0, 0, 0.3)',
              padding: '3px',
              borderRadius: '8px',
            }}
          >
            {[
              { id: 'all', label: 'Hybrid' },
              { id: 'pdf', label: 'PDF Only' },
              { id: 'csv', label: 'CSV Only' },
            ].map((f) => (
              <button
                key={f.id}
                onClick={() => onFilterChange(f.id)}
                style={{
                  padding: '5px 0',
                  fontSize: '11px',
                  fontWeight: 600,
                  borderRadius: '6px',
                  background: activeFilter === f.id ? 'var(--grad-primary)' : 'transparent',
                  color: activeFilter === f.id ? '#ffffff' : 'var(--text-secondary)',
                }}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Upload Dropzone */}
      <div style={{ padding: '16px 20px 12px 20px' }}>
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileSelect}
          accept=".pdf,.csv"
          style={{ display: 'none' }}
        />
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleFileDrop}
          onClick={() => !uploading && fileInputRef.current?.click()}
          style={{
            border: '2px dashed var(--border-hover)',
            borderRadius: 'var(--radius-md)',
            padding: '16px 12px',
            textAlign: 'center',
            cursor: uploading ? 'default' : 'pointer',
            background: 'rgba(255, 255, 255, 0.02)',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--accent-purple)')}
          onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-hover)')}
        >
          {uploading ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
              <Loader2 size={24} className="spin" color="var(--accent-purple)" />
              <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                {uploadStatus}
              </span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
              <Upload size={22} color="var(--text-accent)" />
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                Upload PDF or CSV
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Drag & drop or click to browse
              </div>
            </div>
          )}
        </div>

        {errorMsg && (
          <div
            style={{
              marginTop: '8px',
              padding: '6px 10px',
              borderRadius: '6px',
              background: 'rgba(244, 63, 94, 0.1)',
              border: '1px solid rgba(244, 63, 94, 0.3)',
              color: '#fb7185',
              fontSize: '11px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <AlertCircle size={14} />
            {errorMsg}
          </div>
        )}
      </div>

      {/* Quick Sample Ingestion Shortcuts */}
      <div style={{ padding: '0 20px 14px 20px' }}>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '6px' }}>
          QUICK LOAD SAMPLE DATA
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
          <button
            onClick={() => onLoadSample('pdf')}
            disabled={uploading}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              padding: '6px 8px',
              borderRadius: '6px',
              background: 'rgba(244, 63, 94, 0.1)',
              border: '1px solid rgba(244, 63, 94, 0.25)',
              color: '#fb7185',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            <FileText size={12} /> Load DBMS.pdf
          </button>
          <button
            onClick={() => onLoadSample('csv')}
            disabled={uploading}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              padding: '6px 8px',
              borderRadius: '6px',
              background: 'rgba(16, 185, 129, 0.1)',
              border: '1px solid rgba(16, 185, 129, 0.25)',
              color: '#34d399',
              fontSize: '11px',
              fontWeight: 600,
            }}
          >
            <Table size={12} /> Load Students.csv
          </button>
        </div>
      </div>

      {/* Document Registry List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '0 20px 20px 20px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '11px',
            color: 'var(--text-muted)',
            marginBottom: '8px',
          }}
        >
          <span>INDEXED DOCUMENTS ({documents.length})</span>
        </div>

        {documents.length === 0 ? (
          <div
            style={{
              padding: '24px 12px',
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: '12px',
              border: '1px dashed var(--border-subtle)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            No documents indexed yet. Upload a PDF or CSV above to begin.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {documents.map((doc) => {
              const isPdf = doc.file_type === 'pdf';
              return (
                <div
                  key={doc.document_id}
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    padding: '10px 12px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--border-hover)')}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-subtle)')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                    <div
                      style={{
                        padding: '6px',
                        borderRadius: '6px',
                        background: isPdf ? 'rgba(244, 63, 94, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                        color: isPdf ? '#fb7185' : '#34d399',
                      }}
                    >
                      {isPdf ? <FileText size={16} /> : <FileSpreadsheet size={16} />}
                    </div>
                    <div style={{ overflow: 'hidden' }}>
                      <div
                        style={{
                          fontSize: '13px',
                          fontWeight: 600,
                          color: 'var(--text-primary)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          maxWidth: '160px',
                        }}
                      >
                        {doc.file_name}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {isPdf ? `${doc.page_count || 1} pages • ${doc.chunk_count} chunks` : `${doc.row_count || 0} rows • indexed`}
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={(e) => handleDelete(doc.document_id, e)}
                    style={{
                      background: 'transparent',
                      padding: '6px',
                      borderRadius: '4px',
                      color: 'var(--text-muted)',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#f43f5e')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                    title="Delete document and vector index"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer Info */}
      <div
        style={{
          padding: '12px 20px',
          borderTop: '1px solid var(--border-subtle)',
          fontSize: '11px',
          color: 'var(--text-muted)',
          display: 'flex',
          justifyContent: 'space-between',
        }}
      >
        <span>LLM: {health?.openai_model ? health.openai_model.toUpperCase() : 'OPENAI GPT-4O'}</span>
        <span>ChromaDB local</span>
      </div>
    </aside>
  );
}

