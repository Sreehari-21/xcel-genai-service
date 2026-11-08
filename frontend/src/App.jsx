import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatArea from './components/ChatArea';
import PipelineVisualizer from './components/PipelineVisualizer';
import { fetchHealth, fetchDocuments, queryRAG, loadSampleDocument } from './services/api';

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [health, setHealth] = useState(null);
  const [activeFilter, setActiveFilter] = useState('all'); // 'all', 'pdf', 'csv'
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [visualizerOpen, setVisualizerOpen] = useState(false);
  const [lastTrace, setLastTrace] = useState(null);
  const [lastQuery, setLastQuery] = useState('');
  const [lastResponse, setLastResponse] = useState(null);
  const [conversationId, setConversationId] = useState(() => `conv_${Date.now()}`);

  const loadData = async () => {
    try {
      const [healthData, docsData] = await Promise.all([
        fetchHealth().catch(() => null),
        fetchDocuments().catch(() => ({ documents: [] })),
      ]);
      if (healthData) setHealth(healthData);
      if (docsData?.documents) setDocuments(docsData.documents);
    } catch (err) {
      console.error('Failed to load initial data', err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSendMessage = async (queryText) => {
    if (!queryText.trim() || loading) return;

    // Add user message to feed
    const userMessage = { role: 'user', content: queryText };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);
    setLastQuery(queryText);

    try {
      const filters = activeFilter !== 'all' ? { source_type: activeFilter } : {};
      const response = await queryRAG({
        query: queryText,
        top_k: 8,
        filters,
        conversation_id: conversationId,
      });

      setLastTrace(response.pipeline_trace);
      setLastResponse(response);

      const botMessage = {
        role: 'assistant',
        content: response.answer,
        sources: response.sources || [],
        metadata: response.metadata || {},
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      const errorMessage = {
        role: 'assistant',
        content: `❌ **Error**: ${err.message || 'Failed to generate answer from RAG pipeline.'}`,
        sources: [],
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setConversationId(`conv_${Date.now()}`);
    setLastTrace(null);
    setLastResponse(null);
  };

  const handleLoadSample = async (type) => {
    try {
      const sampleFile = type === 'pdf' ? 'dbms.pdf' : 'students.csv';
      await loadSampleDocument(sampleFile);
      await loadData();
    } catch (err) {
      alert(`Failed to load sample: ${err.message}`);
    }
  };

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden' }}>
      <Sidebar
        documents={documents}
        onDocumentsChange={loadData}
        activeFilter={activeFilter}
        onFilterChange={setActiveFilter}
        health={health}
        onLoadSample={handleLoadSample}
      />
      <ChatArea
        messages={messages}
        onSendMessage={handleSendMessage}
        loading={loading}
        onClearChat={handleClearChat}
        onOpenVisualizer={() => setVisualizerOpen(true)}
        activeFilter={activeFilter}
        hasTrace={Boolean(lastTrace)}
        llmProvider={health?.llm_provider}
      />
      <PipelineVisualizer
        isOpen={visualizerOpen}
        onClose={() => setVisualizerOpen(false)}
        trace={lastTrace}
        lastQuery={lastQuery}
        lastResponse={lastResponse}
      />
    </div>
  );
}
