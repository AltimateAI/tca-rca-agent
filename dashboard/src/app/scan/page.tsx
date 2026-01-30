'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ScanResult {
  queued: number;
  total_found: number;
  timeframe: string;
  issues: Array<{
    id: string;
    title: string;
    priority: number;
    error_count: number;
    user_count: number;
  }>;
}

interface QueuedIssue {
  issue_id: string;
  priority: number;
  error_count: number;
  user_count: number;
  last_seen: string;
  title: string;
  status: string;
  analysis_id?: string;
}

export default function ScanPage() {
  const router = useRouter();
  const [timeframe, setTimeframe] = useState<string>('24h');
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [queue, setQueue] = useState<QueuedIssue[]>([]);
  const [loadingQueue, setLoadingQueue] = useState(false);
  const [batchAnalyzing, setBatchAnalyzing] = useState(false);
  const [batchAnalysisResult, setBatchAnalysisResult] = useState<any>(null);

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    setScanResult(null);

    try {
      const response = await fetch(`${API_BASE}/api/discovery/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          timeframe,
          min_occurrences: 1,  // Changed from 10 to 1 to capture all issues
          auto_analyze: false
        })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Scan failed');
      }

      const data = await response.json();
      setScanResult(data);

      // Refresh queue
      await loadQueue();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setScanning(false);
    }
  };

  const loadQueue = async () => {
    setLoadingQueue(true);
    try {
      const response = await fetch(`${API_BASE}/api/discovery/queue`);
      const data = await response.json();
      setQueue(data);
    } catch (err: any) {
      console.error('Failed to load queue:', err);
    } finally {
      setLoadingQueue(false);
    }
  };

  const analyzeIssue = async (issueId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/discovery/queue/${issueId}/analyze`, {
        method: 'POST'
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Analysis failed to start');
      }

      const data = await response.json();

      // Navigate to analysis page
      router.push(`/analyze/${data.analysis_id}`);
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleBatchAnalyze = async () => {
    setBatchAnalyzing(true);
    setError(null);
    setBatchAnalysisResult(null);

    try {
      // Trigger scan with auto_analyze enabled
      const response = await fetch(`${API_BASE}/api/discovery/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          timeframe,
          min_occurrences: 1,
          auto_analyze: true  // Enable batch analysis with grouping
        })
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Batch analysis failed');
      }

      const data = await response.json();
      setBatchAnalysisResult(data);

      // Refresh queue to show analyzing status
      await loadQueue();

      // Show success message
      alert(`🚀 Batch analysis started for ${data.total_found} issues grouped into ${Object.keys(data.groups).length} error types!`);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBatchAnalyzing(false);
    }
  };

  const getPriorityColor = (priority: number) => {
    if (priority >= 80) return '#dc2626'; // red
    if (priority >= 60) return '#f59e0b'; // orange
    if (priority >= 40) return '#eab308'; // yellow
    return '#22c55e'; // green
  };

  const getPriorityLabel = (priority: number) => {
    if (priority >= 80) return 'Critical';
    if (priority >= 60) return 'High';
    if (priority >= 40) return 'Medium';
    return 'Low';
  };

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(to bottom right, #0f172a, #1e293b, #0f172a)', padding: '2rem' }}>
      <div style={{ maxWidth: '80rem', margin: '0 auto' }}>
        <h1 style={{ fontSize: '1.875rem', fontWeight: 'bold', color: 'white', marginBottom: '2rem' }}>
          🔍 Sentry Issue Scanner
        </h1>

        {/* Scan Controls */}
        <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155', marginBottom: '2rem' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: '600', color: 'white', marginBottom: '1rem' }}>
            Scan Sentry for Issues
          </h2>

          <div style={{ display: 'flex', gap: '1rem', alignItems: 'end', marginBottom: '1rem' }}>
            <div style={{ flex: 1 }}>
              <label style={{ display: 'block', color: '#94a3b8', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                Timeframe
              </label>
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                disabled={scanning}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  background: '#0f172a',
                  color: 'white',
                  border: '1px solid #475569',
                  borderRadius: '0.375rem'
                }}
              >
                <option value="24h">Last 24 hours</option>
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
              </select>
            </div>

            <button
              onClick={handleScan}
              disabled={scanning}
              style={{
                background: scanning ? '#475569' : 'linear-gradient(to right, #3b82f6, #2563eb)',
                color: 'white',
                padding: '0.75rem 1.5rem',
                borderRadius: '0.375rem',
                border: 'none',
                fontWeight: '600',
                cursor: scanning ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                opacity: scanning ? 0.5 : 1
              }}
            >
              {scanning ? (
                <>
                  <div className="spinner" style={{ width: '1rem', height: '1rem', border: '2px solid white', borderTop: '2px solid transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                  Scanning...
                </>
              ) : (
                <>
                  🔍 Scan Sentry
                </>
              )}
            </button>

            <button
              onClick={loadQueue}
              disabled={loadingQueue}
              style={{
                background: '#334155',
                color: 'white',
                padding: '0.75rem 1.5rem',
                borderRadius: '0.375rem',
                border: '1px solid #475569',
                fontWeight: '600',
                cursor: loadingQueue ? 'not-allowed' : 'pointer',
                opacity: loadingQueue ? 0.5 : 1
              }}
            >
              {loadingQueue ? 'Loading...' : '🔄 Refresh Queue'}
            </button>
          </div>

          {error && (
            <div style={{ background: 'rgba(220, 38, 38, 0.2)', border: '1px solid #dc2626', padding: '1rem', borderRadius: '0.25rem' }}>
              <p style={{ color: '#fca5a5', fontSize: '0.875rem' }}>{error}</p>
            </div>
          )}

          {scanResult && (
            <div style={{ background: 'rgba(34, 197, 94, 0.2)', border: '1px solid #22c55e', padding: '1rem', borderRadius: '0.25rem', marginBottom: '1rem' }}>
              <p style={{ color: '#bbf7d0', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                ✅ Found {scanResult.total_found} issues, queued {scanResult.queued} new issues
              </p>
              {scanResult.groups && Object.keys(scanResult.groups).length > 0 && (
                <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(34, 197, 94, 0.3)' }}>
                  <p style={{ color: '#bbf7d0', fontSize: '0.75rem', marginBottom: '0.5rem', fontWeight: '600' }}>
                    📊 Issue Groups:
                  </p>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {Object.entries(scanResult.groups).map(([errorType, count]) => (
                      <span
                        key={errorType}
                        style={{
                          background: 'rgba(34, 197, 94, 0.3)',
                          padding: '0.25rem 0.75rem',
                          borderRadius: '0.25rem',
                          fontSize: '0.75rem',
                          color: '#bbf7d0'
                        }}
                      >
                        {errorType}: {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {scanResult && scanResult.total_found > 0 && (
            <button
              onClick={handleBatchAnalyze}
              disabled={batchAnalyzing}
              style={{
                width: '100%',
                background: batchAnalyzing ? '#475569' : 'linear-gradient(to right, #8b5cf6, #6d28d9)',
                color: 'white',
                padding: '1rem',
                borderRadius: '0.375rem',
                border: 'none',
                fontWeight: '600',
                cursor: batchAnalyzing ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                opacity: batchAnalyzing ? 0.5 : 1,
                fontSize: '1rem'
              }}
            >
              {batchAnalyzing ? (
                <>
                  <div className="spinner" style={{ width: '1.25rem', height: '1.25rem', border: '2px solid white', borderTop: '2px solid transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                  Starting Batch Analysis...
                </>
              ) : (
                <>
                  🚀 Batch Analyze All Issues ({scanResult.total_found} issues in {Object.keys(scanResult.groups).length} groups)
                </>
              )}
            </button>
          )}

          {batchAnalysisResult && (
            <div style={{ marginTop: '1rem', background: 'rgba(139, 92, 246, 0.2)', border: '1px solid #8b5cf6', padding: '1rem', borderRadius: '0.25rem' }}>
              <p style={{ color: '#ddd6fe', fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.5rem' }}>
                🚀 Batch Analysis Started!
              </p>
              <p style={{ color: '#ddd6fe', fontSize: '0.875rem' }}>
                Analyzing {batchAnalysisResult.total_found} issues grouped by error type. Using prompt caching for cost efficiency.
              </p>
              {batchAnalysisResult.groups && (
                <div style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(139, 92, 246, 0.3)' }}>
                  {Object.entries(batchAnalysisResult.groups).map(([errorType, count]: [string, any]) => (
                    <p key={errorType} style={{ color: '#ddd6fe', fontSize: '0.75rem' }}>
                      • {errorType}: {count} issues (batch analysis with shared context)
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Queue */}
        <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: '600', color: 'white', marginBottom: '1rem' }}>
            Analysis Queue ({queue.length})
          </h2>

          {queue.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: '0.875rem', textAlign: 'center', padding: '2rem' }}>
              No issues in queue. Run a scan to discover issues.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {queue.map((issue) => (
                <div
                  key={issue.issue_id}
                  style={{
                    background: '#0f172a',
                    padding: '1rem',
                    borderRadius: '0.375rem',
                    border: '1px solid #475569',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                      <div
                        style={{
                          background: getPriorityColor(issue.priority),
                          color: 'white',
                          padding: '0.25rem 0.5rem',
                          borderRadius: '0.25rem',
                          fontSize: '0.75rem',
                          fontWeight: '600'
                        }}
                      >
                        {getPriorityLabel(issue.priority)} ({issue.priority})
                      </div>
                      <h3 style={{ color: 'white', fontSize: '0.875rem', fontWeight: '600' }}>
                        {issue.title}
                      </h3>
                    </div>
                    <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.75rem', color: '#94a3b8' }}>
                      <span>ID: {issue.issue_id}</span>
                      <span>📊 {issue.error_count} errors</span>
                      <span>👥 {issue.user_count} users</span>
                      <span>Status: {issue.status}</span>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {issue.status === 'queued' && (
                      <button
                        onClick={() => analyzeIssue(issue.issue_id)}
                        style={{
                          background: 'linear-gradient(to right, #3b82f6, #2563eb)',
                          color: 'white',
                          padding: '0.5rem 1rem',
                          borderRadius: '0.25rem',
                          border: 'none',
                          fontSize: '0.875rem',
                          fontWeight: '600',
                          cursor: 'pointer'
                        }}
                      >
                        ▶️ Analyze
                      </button>
                    )}

                    {issue.status === 'analyzing' && issue.analysis_id && (
                      <button
                        onClick={() => router.push(`/analyze/${issue.analysis_id}`)}
                        style={{
                          background: '#334155',
                          color: 'white',
                          padding: '0.5rem 1rem',
                          borderRadius: '0.25rem',
                          border: '1px solid #475569',
                          fontSize: '0.875rem',
                          fontWeight: '600',
                          cursor: 'pointer'
                        }}
                      >
                        👁️ View
                      </button>
                    )}

                    {issue.status === 'completed' && issue.analysis_id && (
                      <button
                        onClick={() => router.push(`/analyze/${issue.analysis_id}`)}
                        style={{
                          background: 'rgba(34, 197, 94, 0.3)',
                          color: '#bbf7d0',
                          padding: '0.5rem 1rem',
                          borderRadius: '0.25rem',
                          border: '1px solid #22c55e',
                          fontSize: '0.875rem',
                          fontWeight: '600',
                          cursor: 'pointer'
                        }}
                      >
                        ✅ View Result
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Back Link */}
        <div style={{ marginTop: '2rem', textAlign: 'center' }}>
          <a href="/" style={{ color: '#60a5fa', textDecoration: 'underline' }}>
            ← Back to Home
          </a>
        </div>
      </div>

      <style jsx>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
