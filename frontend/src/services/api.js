const API_BASE = '';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function fetchDocuments() {
  const res = await fetch(`${API_BASE}/documents`);
  if (!res.ok) throw new Error('Failed to fetch documents');
  return res.json();
}

export async function deleteDocument(documentId) {
  const res = await fetch(`${API_BASE}/documents/${documentId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete document');
  return res.json();
}

export async function uploadFile(file, type = 'pdf') {
  const formData = new FormData();
  formData.append('file', file);

  const endpoint = type === 'pdf' ? '/upload/pdf' : '/upload/csv';
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Upload failed with status ${res.status}`);
  }

  return res.json();
}

export async function loadSampleDocument(sampleName) {
  const res = await fetch(`${API_BASE}/upload/sample/${encodeURIComponent(sampleName)}`, {
    method: 'POST',
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to load sample ${sampleName}`);
  }
  return res.json();
}


export async function queryRAG({ query, top_k = 8, filters = {}, conversation_id = null }) {
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      top_k,
      filters,
      conversation_id,
    }),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Query failed with status ${res.status}`);
  }

  return res.json();
}

export async function fetchQueryTrace(requestId) {
  const res = await fetch(`${API_BASE}/api/v1/query/${requestId}/trace`);
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch trace for ${requestId}`);
  }
  return res.json();
}
