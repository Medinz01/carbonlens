import React, { useState } from 'react';
import { downloadPDF, downloadCBAM } from '../utils/api';

const ExportPanel = ({ jobId }) => {
  const [pdfLoading, setPdfLoading] = useState(false);
  const [cbamLoading, setCbamLoading] = useState(false);
  const [error, setError] = useState(null);

  const handlePDF = async () => {
    setPdfLoading(true);
    setError(null);
    try {
      await downloadPDF(jobId);
    } catch (err) {
      setError('PDF export failed: ' + err.message);
    } finally {
      setPdfLoading(false);
    }
  };

  const handleCBAM = async () => {
    setCbamLoading(true);
    setError(null);
    try {
      await downloadCBAM(jobId);
    } catch (err) {
      setError('CBAM export failed: ' + err.message);
    } finally {
      setCbamLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col sm:flex-row gap-4">
        <button
          onClick={handlePDF}
          disabled={pdfLoading}
          className="px-6 py-2 rounded-full text-sm font-medium transition-all bg-white/5 border border-white/10 text-white hover:bg-white/10 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {pdfLoading ? (
            <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
          ) : <span className="opacity-70">📄</span>}
          Download PDF
        </button>

        <button
          onClick={handleCBAM}
          disabled={cbamLoading}
          className="px-6 py-2 rounded-full text-sm font-medium transition-all bg-orange-500/10 border border-orange-500/30 text-orange-50 hover:bg-orange-500/20 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {cbamLoading ? (
            <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
            </svg>
          ) : <span className="opacity-70">📦</span>}
          Export CBAM JSON
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
          ⚠ {error}
        </p>
      )}
    </div>
  );
};

export default ExportPanel;