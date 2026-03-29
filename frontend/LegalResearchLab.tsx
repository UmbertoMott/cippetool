/**
 * CIPP/E Legal Research Lab — React Component
 * Two-column interface: Document library (left) + Analysis panel (right)
 * Integrates with FastAPI backend (/api/documents, /api/documents/extract-text, etc.)
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import './LegalResearchLab.css';

// Types
interface PDFDocument {
  name: string;
  display_name: string;
  size_bytes: number;
  size_mb: number;
  updated: string;
  content_type: string;
  metadata?: Record<string, unknown>;
  isGCS?: boolean;
  gcs_blob?: string;
}

interface Highlight {
  num: number;
  text: string;
}

interface AnalysisSection {
  title: string;
  content: string;
}

interface RatioLegisComment {
  num: number;
  title: string;
  explanation: string;
}

// Main Component
const LegalResearchLab: React.FC = () => {
  // State
  const [documents, setDocuments] = useState<PDFDocument[]>([]);
  const [selectedDoc, setSelectedDoc] = useState<PDFDocument | null>(null);
  const [documentText, setDocumentText] = useState<string>('');
  const [isLoadingDoc, setIsLoadingDoc] = useState(false);
  const [analysisQuery, setAnalysisQuery] = useState('');
  const [analysis, setAnalysis] = useState<string>('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [activeTab, setActiveTab] = useState<'library' | 'analysis'>('library');

  const rightPanelRef = useRef<HTMLDivElement>(null);

  // Load documents on mount
  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const response = await fetch('/api/documents?limit=50');
      const data = await response.json();
      setDocuments(data.documents || []);
    } catch (error) {
      console.error('Error loading documents:', error);
    }
  };

  // Load document text
  const handleSelectDocument = async (doc: PDFDocument) => {
    setSelectedDoc(doc);
    setIsLoadingDoc(true);
    setDocumentText('');
    setHighlights([]);
    setAnalysis('');

    try {
      const response = await fetch('/api/documents/ai-context', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await response.json();

      if (data.text) {
        setDocumentText(data.text);
      }
    } catch (error) {
      console.error('Error loading document:', error);
      setDocumentText('Errore nel caricamento del documento.');
    } finally {
      setIsLoadingDoc(false);
    }
  };

  // Analyze document with Gemini
  const handleAnalyze = async () => {
    if (!selectedDoc || !analysisQuery.trim()) {
      alert('Seleziona un documento e inserisci una domanda.');
      return;
    }

    setIsAnalyzing(true);
    setAnalysis('');
    setHighlights([]);

    try {
      // Call your backend endpoint that handles Gemini analysis
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_text: documentText,
          query: analysisQuery,
          blob_name: selectedDoc.gcs_blob || selectedDoc.name,
        }),
      });

      const data = await response.json();

      if (data.analysis) {
        setAnalysis(data.analysis);
        // Extract highlights from analysis if present
        extractHighlightsFromAnalysis(data.analysis);
      }
    } catch (error) {
      console.error('Error analyzing document:', error);
      setAnalysis('Errore nell\'analisi. Riprova.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Extract numbered highlights [HL:N: text] from analysis
  const extractHighlightsFromAnalysis = (text: string) => {
    const regex = /\[HL:(\d+):\s*([^\]]{5,100})\]/g;
    const found: Highlight[] = [];
    let match;

    while ((match = regex.exec(text)) !== null) {
      found.push({
        num: parseInt(match[1]),
        text: match[2].trim(),
      });
    }

    setHighlights(found);
  };

  // Find highlights in selected document
  const handleFindHighlights = async () => {
    if (!selectedDoc || highlights.length === 0) return;

    try {
      const searchTexts = highlights.map((h) => h.text);
      const response = await fetch('/api/documents/highlights', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          blob_name: selectedDoc.gcs_blob || selectedDoc.name,
          search_texts: searchTexts,
        }),
      });

      const data = await response.json();
      // Handle highlight positions (integrate with PDF.js viewer)
      console.log('Highlight positions:', data);
    } catch (error) {
      console.error('Error finding highlights:', error);
    }
  };

  // Render analysis with numbered comments, tables, and schemas
  const renderAnalysis = (text: string) => {
    return (
      <div className="lrl-analysis-content">
        {text.split('\n').map((line, idx) => {
          // Numbered comments ①②③
          if (/^[①②③④⑤⑥⑦⑧⑨⑩]/.test(line)) {
            const match = line.match(/^([①②③④⑤⑥⑦⑧⑨⑩])\s*(.*)/);
            if (match) {
              return (
                <div key={idx} className="lrl-num-comment">
                  <span className="lrl-num-badge">{match[1]}</span>
                  <div className="lrl-num-content">{match[2]}</div>
                </div>
              );
            }
          }

          // Headers (###, ##, #)
          if (line.startsWith('###')) {
            return (
              <h3 key={idx} className="lrl-h3">
                {line.replace(/^#+\s*/, '')}
              </h3>
            );
          }
          if (line.startsWith('##')) {
            return (
              <h2 key={idx} className="lrl-h2">
                {line.replace(/^#+\s*/, '')}
              </h2>
            );
          }
          if (line.startsWith('#')) {
            return (
              <h1 key={idx} className="lrl-h1">
                {line.replace(/^#+\s*/, '')}
              </h1>
            );
          }

          // Empty lines
          if (!line.trim()) {
            return <div key={idx} className="lrl-spacer" />;
          }

          // Regular paragraphs
          return (
            <p key={idx} className="lrl-p">
              {line}
            </p>
          );
        })}
      </div>
    );
  };

  return (
    <div className="lrl-container">
      {/* Left Panel — Document Library */}
      <div className="lrl-left-panel">
        <div className="lrl-panel-header">
          <h2>📚 Biblioteca Documenti</h2>
          <span className="lrl-doc-count">{documents.length}</span>
        </div>

        <div className="lrl-doc-list">
          {documents.map((doc, idx) => (
            <div
              key={idx}
              className={`lrl-doc-item ${selectedDoc?.name === doc.name ? 'active' : ''}`}
              onClick={() => handleSelectDocument(doc)}
            >
              <div className="lrl-doc-title">{doc.display_name}</div>
              <div className="lrl-doc-meta">
                {doc.size_mb && <span>{doc.size_mb} MB</span>}
                {doc.isGCS && <span className="lrl-badge-gcs">☁️ GCS</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right Panel — Analysis & Viewer */}
      <div className="lrl-right-panel" ref={rightPanelRef}>
        <div className="lrl-tabs">
          <button
            className={`lrl-tab ${activeTab === 'library' ? 'active' : ''}`}
            onClick={() => setActiveTab('library')}
          >
            📄 Documento
          </button>
          <button
            className={`lrl-tab ${activeTab === 'analysis' ? 'active' : ''}`}
            onClick={() => setActiveTab('analysis')}
          >
            🔍 Analisi
          </button>
        </div>

        {activeTab === 'library' && (
          <div className="lrl-viewer-section">
            {isLoadingDoc ? (
              <div className="lrl-loading">Caricamento documento...</div>
            ) : selectedDoc ? (
              <div className="lrl-doc-viewer">
                <div className="lrl-doc-viewer-header">
                  <h3>{selectedDoc.display_name}</h3>
                  {highlights.length > 0 && (
                    <button
                      className="lrl-btn-highlight"
                      onClick={handleFindHighlights}
                    >
                      Evidenzia ({highlights.length})
                    </button>
                  )}
                </div>
                <div className="lrl-doc-text">
                  {documentText.substring(0, 5000)}
                  {documentText.length > 5000 && (
                    <div className="lrl-text-truncated">
                      ... (testo troncato, {documentText.length} caratteri totali)
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="lrl-placeholder">
                Seleziona un documento dalla libreria
              </div>
            )}
          </div>
        )}

        {activeTab === 'analysis' && (
          <div className="lrl-analysis-section">
            <div className="lrl-query-box">
              <textarea
                className="lrl-query-input"
                placeholder="Fai una domanda sui documenti aperti... es: 'Quali sono i diritti GDPR dell'interessato?'"
                value={analysisQuery}
                onChange={(e) => setAnalysisQuery(e.target.value)}
              />
              <button
                className="lrl-btn-analyze"
                onClick={handleAnalyze}
                disabled={isAnalyzing}
              >
                {isAnalyzing ? 'Analisi in corso...' : '🚀 Analizza'}
              </button>
            </div>

            {analysis && (
              <div className="lrl-analysis-output">
                <div className="lrl-analysis-header">
                  <h3>Analisi Strutturata</h3>
                  <button
                    className="lrl-btn-copy"
                    onClick={() => navigator.clipboard.writeText(analysis)}
                  >
                    📋 Copia
                  </button>
                </div>
                {renderAnalysis(analysis)}
              </div>
            )}

            {!analysis && !isAnalyzing && (
              <div className="lrl-placeholder">
                Scrivi una domanda e fai clic su "Analizza" per iniziare
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default LegalResearchLab;
