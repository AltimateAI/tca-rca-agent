'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { api, RCAResult, RCAStreamEvent } from '../../../lib/api';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ReactDiffViewer from 'react-diff-viewer-continued';

export default function AnalyzePage() {
  const params = useParams();
  const analysisId = params.id as string;

  const [progress, setProgress] = useState<string[]>([]);
  const [result, setResult] = useState<RCAResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creatingPR, setCreatingPR] = useState(false);
  const [prResult, setPRResult] = useState<{ pr_url: string; pr_number: number; branch: string } | null>(null);
  const [prError, setPRError] = useState<string | null>(null);
  const [showDiff, setShowDiff] = useState(false);
  const [prStatus, setPRStatus] = useState<any>(null);
  const [checkingPRStatus, setCheckingPRStatus] = useState(false);
  const [prStatusError, setPRStatusError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelled, setCancelled] = useState(false);

  useEffect(() => {
    const loadAnalysis = async () => {
      try {
        // First, try to get cached result
        const historyResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/rca/history`);
        if (historyResponse.ok) {
          const history = await historyResponse.json();
          const cachedAnalysis = history.find((item: any) => item.id === analysisId);

          if (cachedAnalysis && cachedAnalysis.status === 'completed' && cachedAnalysis.result) {
            // Use cached result - show immediately without re-analyzing!
            console.log('✅ Using cached result for analysis:', analysisId);
            setResult(cachedAnalysis.result);
            setLoading(false);
            return;
          }
        }

        // No cached result, connect to stream
        await api.streamAnalysis(analysisId, (event: RCAStreamEvent) => {
          if (event.type === 'progress') {
            setProgress((prev) => [...prev, event.data.message]);
          } else if (event.type === 'result') {
            setResult(event.data);
            setLoading(false);
          } else if (event.type === 'error') {
            setError(event.data.message);
            setLoading(false);
          }
        });
      } catch (err: any) {
        setError(err.message);
        setLoading(false);
      }
    };

    loadAnalysis();
  }, [analysisId]);

  const checkPRStatus = async () => {
    setCheckingPRStatus(true);
    setPRStatusError(null);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/rca/${analysisId}/pr-status`);

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to check PR status');
      }

      const status = await response.json();
      setPRStatus(status);
    } catch (err: any) {
      setPRStatusError(err.message);
    } finally {
      setCheckingPRStatus(false);
    }
  };

  const cancelAnalysis = async () => {
    if (!confirm('Are you sure you want to cancel this analysis? This will stop the Claude agent and prevent further credit usage.')) {
      return;
    }

    setCancelling(true);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/rca/${analysisId}/cancel`,
        { method: 'POST' }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to cancel analysis');
      }

      const data = await response.json();
      setCancelled(true);
      setError(`Analysis cancelled: ${data.message}`);
      setLoading(false);
    } catch (err: any) {
      setError(`Failed to cancel: ${err.message}`);
    } finally {
      setCancelling(false);
    }
  };

  const getPRStateColor = (state: string) => {
    if (state === 'merged') return '#22c55e';
    if (state === 'open') return '#3b82f6';
    return '#6b7280';
  };

  const getPRStateIcon = (state: string) => {
    if (state === 'merged') return '✅';
    if (state === 'open') return '🔄';
    return '❌';
  };

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(to bottom right, #0f172a, #1e293b, #0f172a)', padding: '2rem' }}>
      <div style={{ maxWidth: '64rem', margin: '0 auto' }}>
        <h1 style={{ fontSize: '1.875rem', fontWeight: 'bold', color: 'white', marginBottom: '2rem' }}>
          Analysis: {analysisId.slice(0, 8)}...
        </h1>

        {/* Progress Log */}
        {loading && !cancelled && (
          <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155', marginBottom: '2rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div className="spinner" style={{ width: '1.5rem', height: '1.5rem', border: '2px solid #3b82f6', borderTop: '2px solid transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                <h2 style={{ fontSize: '1.25rem', fontWeight: '600', color: 'white' }}>
                  Analyzing...
                </h2>
              </div>

              {/* Cancel Button */}
              <button
                onClick={cancelAnalysis}
                disabled={cancelling}
                style={{
                  background: cancelling ? '#475569' : 'linear-gradient(to right, #dc2626, #991b1b)',
                  color: 'white',
                  padding: '0.5rem 1rem',
                  borderRadius: '0.375rem',
                  border: 'none',
                  fontWeight: '600',
                  cursor: cancelling ? 'not-allowed' : 'pointer',
                  opacity: cancelling ? 0.5 : 1,
                  fontSize: '0.875rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem'
                }}
              >
                {cancelling ? (
                  <>
                    <div className="spinner" style={{ width: '1rem', height: '1rem', border: '2px solid white', borderTop: '2px solid transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                    Cancelling...
                  </>
                ) : (
                  <>
                    🛑 Cancel Analysis
                  </>
                )}
              </button>
            </div>

            <div style={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
              {progress.map((msg, idx) => (
                <div key={idx} style={{ color: '#cbd5e1', marginBottom: '0.5rem' }}>
                  <span style={{ color: '#64748b' }}>[{idx + 1}]</span> {msg}
                </div>
              ))}
            </div>

            <div style={{ marginTop: '1rem', padding: '0.75rem', background: 'rgba(234, 179, 8, 0.1)', border: '1px solid rgba(234, 179, 8, 0.3)', borderRadius: '0.25rem' }}>
              <p style={{ color: '#fde047', fontSize: '0.875rem', margin: 0 }}>
                ⚠️ If analysis is taking too long or stuck, click Cancel to stop the Claude agent and prevent credit consumption.
              </p>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{ background: 'rgba(220, 38, 38, 0.2)', border: '1px solid #dc2626', padding: '1.5rem', borderRadius: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
              <span style={{ fontSize: '1.5rem' }}>❌</span>
              <h2 style={{ fontSize: '1.25rem', fontWeight: '600', color: '#fca5a5' }}>
                Analysis Failed
              </h2>
            </div>
            <p style={{ color: '#fecaca' }}>{error}</p>
          </div>
        )}

        {/* Result */}
        {result && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Success Header */}
            <div style={{ background: 'rgba(34, 197, 94, 0.2)', border: '1px solid #22c55e', padding: '1.5rem', borderRadius: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span style={{ fontSize: '1.5rem' }}>✅</span>
                <div>
                  <h2 style={{ fontSize: '1.25rem', fontWeight: '600', color: '#86efac' }}>
                    Analysis Complete
                  </h2>
                  <p style={{ color: '#bbf7d0', fontSize: '0.875rem' }}>
                    {result.analysis_time_seconds && `Completed in ${result.analysis_time_seconds.toFixed(1)}s • `}
                    Confidence: {(result.confidence * 100).toFixed(0)}%
                  </p>
                </div>
              </div>
            </div>

            {/* Root Cause */}
            <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
              <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'white', marginBottom: '0.75rem' }}>
                Root Cause
              </h3>
              <p style={{ color: '#cbd5e1', lineHeight: '1.6' }}>
                {result.root_cause}
              </p>
            </div>

            {/* Fix Explanation */}
            <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
              <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'white', marginBottom: '0.75rem' }}>
                Fix Explanation
              </h3>
              <p style={{ color: '#cbd5e1', lineHeight: '1.6' }}>
                {result.fix_explanation}
              </p>
              <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginTop: '0.5rem' }}>
                File: <code style={{ color: '#60a5fa' }}>{result.file_path}</code>
              </p>
            </div>

            {/* Fix Code with Syntax Highlighting */}
            <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'white' }}>
                  Fix Code
                </h3>
                <button
                  onClick={() => setShowDiff(!showDiff)}
                  style={{
                    background: showDiff ? '#3b82f6' : '#334155',
                    color: 'white',
                    padding: '0.5rem 1rem',
                    borderRadius: '0.25rem',
                    border: '1px solid #475569',
                    fontSize: '0.875rem',
                    fontWeight: '600',
                    cursor: 'pointer',
                    transition: 'all 0.2s'
                  }}
                >
                  {showDiff ? '📝 Show Fix Only' : '🔄 Show Before/After'}
                </button>
              </div>

              {!showDiff ? (
                <div style={{ borderRadius: '0.5rem', overflow: 'hidden' }}>
                  <SyntaxHighlighter
                    language="python"
                    style={vscDarkPlus}
                    customStyle={{
                      margin: 0,
                      padding: '1rem',
                      fontSize: '0.875rem',
                      background: '#1e1e1e'
                    }}
                    showLineNumbers
                  >
                    {result.fix_code}
                  </SyntaxHighlighter>
                </div>
              ) : (
                <div style={{ borderRadius: '0.5rem', overflow: 'hidden' }}>
                  <ReactDiffViewer
                    oldValue={(result as any).original_function || (result as any).original_code || '// Original code not available'}
                    newValue={result.fix_code}
                    splitView={true}
                    showDiffOnly={false}
                    useDarkTheme={true}
                    leftTitle="❌ Before (Buggy)"
                    rightTitle="✅ After (Fixed)"
                    styles={{
                      variables: {
                        dark: {
                          diffViewerBackground: '#1e1e1e',
                          addedBackground: '#1a3a1a',
                          addedColor: '#a6e3a1',
                          removedBackground: '#3a1a1a',
                          removedColor: '#f38ba8',
                          wordAddedBackground: '#2d5a2d',
                          wordRemovedBackground: '#5a2d2d',
                          codeFoldBackground: '#262626',
                          emptyLineBackground: '#1e1e1e',
                        }
                      },
                      line: {
                        fontSize: '0.875rem',
                        fontFamily: 'monospace'
                      }
                    }}
                  />
                </div>
              )}
            </div>

            {/* Test Code with Syntax Highlighting */}
            <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
              <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'white', marginBottom: '0.75rem' }}>
                Test Case
              </h3>
              <div style={{ borderRadius: '0.5rem', overflow: 'hidden' }}>
                <SyntaxHighlighter
                  language="python"
                  style={vscDarkPlus}
                  customStyle={{
                    margin: 0,
                    padding: '1rem',
                    fontSize: '0.875rem',
                    background: '#1e1e1e'
                  }}
                  showLineNumbers
                >
                  {result.test_code}
                </SyntaxHighlighter>
              </div>
            </div>

            {/* Evidence Section */}
            {result.evidence && (
              <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
                <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'white', marginBottom: '0.75rem' }}>
                  📊 Evidence Collected
                </h3>

                {result.infrastructure_correlation !== undefined && result.infrastructure_correlation !== null && (
                  <div style={{ marginBottom: '1rem', padding: '0.75rem', background: 'rgba(59, 130, 246, 0.1)', borderRadius: '0.375rem', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
                    <p style={{ color: '#cbd5e1', fontSize: '0.875rem', marginBottom: '0.25rem' }}>
                      <strong>Infrastructure Correlation:</strong> {(result.infrastructure_correlation * 100).toFixed(0)}%
                    </p>
                    {result.user_impact_score !== undefined && result.user_impact_score !== null && (
                      <p style={{ color: '#cbd5e1', fontSize: '0.875rem' }}>
                        <strong>User Impact Score:</strong> {result.user_impact_score.toFixed(1)}/100
                      </p>
                    )}
                  </div>
                )}

                {result.evidence.signoz_metrics && (
                  <details style={{ marginBottom: '1rem', cursor: 'pointer' }}>
                    <summary style={{ color: '#60a5fa', fontWeight: '600', marginBottom: '0.5rem', userSelect: 'none' }}>
                      🏗️ Infrastructure (SignOz)
                    </summary>
                    <pre style={{ background: '#0f172a', padding: '1rem', borderRadius: '0.25rem', border: '1px solid #475569', overflowX: 'auto', marginTop: '0.5rem' }}>
                      <code style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>
                        {JSON.stringify(result.evidence.signoz_metrics, null, 2)}
                      </code>
                    </pre>
                  </details>
                )}

                {result.evidence.posthog_sessions && (
                  <details style={{ marginBottom: '1rem', cursor: 'pointer' }}>
                    <summary style={{ color: '#60a5fa', fontWeight: '600', marginBottom: '0.5rem', userSelect: 'none' }}>
                      👥 User Impact (PostHog)
                    </summary>
                    <pre style={{ background: '#0f172a', padding: '1rem', borderRadius: '0.25rem', border: '1px solid #475569', overflowX: 'auto', marginTop: '0.5rem' }}>
                      <code style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>
                        {JSON.stringify(result.evidence.posthog_sessions, null, 2)}
                      </code>
                    </pre>
                  </details>
                )}

                {result.evidence.aws_logs && (
                  <details style={{ marginBottom: '1rem', cursor: 'pointer' }}>
                    <summary style={{ color: '#60a5fa', fontWeight: '600', marginBottom: '0.5rem', userSelect: 'none' }}>
                      ☁️ AWS Logs
                    </summary>
                    <pre style={{ background: '#0f172a', padding: '1rem', borderRadius: '0.25rem', border: '1px solid #475569', overflowX: 'auto', marginTop: '0.5rem' }}>
                      <code style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>
                        {JSON.stringify(result.evidence.aws_logs, null, 2)}
                      </code>
                    </pre>
                  </details>
                )}

                {result.evidence.github_context && (
                  <details style={{ marginBottom: '0', cursor: 'pointer' }}>
                    <summary style={{ color: '#60a5fa', fontWeight: '600', marginBottom: '0.5rem', userSelect: 'none' }}>
                      📁 GitHub Context
                    </summary>
                    <pre style={{ background: '#0f172a', padding: '1rem', borderRadius: '0.25rem', border: '1px solid #475569', overflowX: 'auto', marginTop: '0.5rem' }}>
                      <code style={{ fontSize: '0.75rem', color: '#cbd5e1' }}>
                        {JSON.stringify(result.evidence.github_context, null, 2)}
                      </code>
                    </pre>
                  </details>
                )}
              </div>
            )}

            {/* PR Creation Section */}
            {result.confidence >= 0.5 && !prResult && (
              <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
                <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'white', marginBottom: '0.75rem' }}>
                  Create Pull Request
                </h3>
                <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '1rem' }}>
                  Fix confidence is {(result.confidence * 100).toFixed(0)}% - high enough to automatically create a PR.
                </p>
                
                {prError && (
                  <div style={{ background: 'rgba(220, 38, 38, 0.2)', border: '1px solid #dc2626', padding: '1rem', borderRadius: '0.25rem', marginBottom: '1rem' }}>
                    <p style={{ color: '#fca5a5', fontSize: '0.875rem' }}>{prError}</p>
                  </div>
                )}

                <button
                  onClick={async () => {
                    setCreatingPR(true);
                    setPRError(null);
                    try {
                      const response = await api.createPR(analysisId);

                      // If PR creation started, poll for status
                      if (response.status === 'creating') {
                        console.log('PR creation started, polling for status...');

                        // Poll every 2 seconds for up to 2 minutes
                        for (let i = 0; i < 60; i++) {
                          await new Promise(resolve => setTimeout(resolve, 2000));

                          // Fetch updated analysis
                          const historyResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/rca/history`);
                          if (historyResponse.ok) {
                            const history = await historyResponse.json();
                            const analysis = history.find((item: any) => item.id === analysisId);

                            if (analysis?.pr_status === 'created' && analysis.pr_url) {
                              setPRResult({
                                pr_url: analysis.pr_url,
                                pr_number: analysis.pr_number,
                                branch: analysis.pr_branch || 'unknown'
                              });
                              setCreatingPR(false);
                              return;
                            } else if (analysis?.pr_status === 'failed') {
                              setPRError(analysis.pr_error || 'PR creation failed');
                              setCreatingPR(false);
                              return;
                            }
                          }
                        }

                        // Timeout after 2 minutes
                        setPRError('PR creation timed out. Please check back later or check GitHub directly.');
                        setCreatingPR(false);
                      } else if (response.status === 'exists') {
                        // PR already exists
                        setPRResult({
                          pr_url: response.pr_url,
                          pr_number: response.pr_number,
                          branch: 'existing'
                        });
                      } else {
                        // Immediate success (shouldn't happen with new flow, but handle it)
                        setPRResult(response);
                      }
                    } catch (err: any) {
                      setPRError(err.response?.data?.detail || err.message || 'Failed to create PR');
                      setCreatingPR(false);
                    }
                  }}
                  disabled={creatingPR}
                  style={{
                    background: creatingPR ? '#475569' : 'linear-gradient(to right, #3b82f6, #2563eb)',
                    color: 'white',
                    padding: '0.75rem 1.5rem',
                    borderRadius: '0.375rem',
                    border: 'none',
                    fontWeight: '600',
                    cursor: creatingPR ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    opacity: creatingPR ? 0.5 : 1,
                    transition: 'all 0.2s'
                  }}
                >
                  {creatingPR ? (
                    <>
                      <div className="spinner" style={{ width: '1rem', height: '1rem', border: '2px solid white', borderTop: '2px solid transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                      Creating PR...
                    </>
                  ) : (
                    <>
                      🚀 Create Pull Request
                    </>
                  )}
                </button>
              </div>
            )}

            {/* PR Success */}
            {prResult && (
              <div style={{ background: 'rgba(34, 197, 94, 0.2)', border: '1px solid #22c55e', padding: '1.5rem', borderRadius: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                  <span style={{ fontSize: '1.5rem' }}>🎉</span>
                  <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: '#86efac' }}>
                    Pull Request Created!
                  </h3>
                </div>
                <p style={{ color: '#bbf7d0', marginBottom: '0.5rem' }}>
                  <strong>Branch:</strong> <code style={{ background: '#0f172a', padding: '0.25rem 0.5rem', borderRadius: '0.25rem' }}>{prResult.branch}</code>
                </p>
                <p style={{ color: '#bbf7d0', marginBottom: '1rem' }}>
                  <strong>PR #{prResult.pr_number}</strong>
                </p>

                <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
                  <a
                    href={prResult.pr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'inline-block',
                      background: 'rgba(34, 197, 94, 0.3)',
                      color: '#bbf7d0',
                      padding: '0.75rem 1.5rem',
                      borderRadius: '0.375rem',
                      textDecoration: 'none',
                      fontWeight: '600',
                      border: '1px solid #22c55e'
                    }}
                  >
                    View Pull Request →
                  </a>

                  <button
                    onClick={checkPRStatus}
                    disabled={checkingPRStatus}
                    style={{
                      background: checkingPRStatus ? '#475569' : 'rgba(59, 130, 246, 0.3)',
                      color: checkingPRStatus ? '#94a3b8' : '#93c5fd',
                      padding: '0.75rem 1.5rem',
                      borderRadius: '0.375rem',
                      border: checkingPRStatus ? '1px solid #475569' : '1px solid #3b82f6',
                      fontWeight: '600',
                      cursor: checkingPRStatus ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.5rem'
                    }}
                  >
                    {checkingPRStatus ? (
                      <>
                        <div className="spinner" style={{ width: '1rem', height: '1rem', border: '2px solid #93c5fd', borderTop: '2px solid transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                        Checking...
                      </>
                    ) : (
                      <>
                        🔄 Recheck PR Status
                      </>
                    )}
                  </button>
                </div>

                {/* PR Status Display */}
                {prStatus && (
                  <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(15, 23, 42, 0.5)', borderRadius: '0.375rem', border: '1px solid #334155' }}>
                    <h4 style={{ fontSize: '1rem', fontWeight: '600', color: '#cbd5e1', marginBottom: '0.75rem' }}>
                      📊 PR Status
                    </h4>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {/* State */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontSize: '1.25rem' }}>{getPRStateIcon(prStatus.state)}</span>
                        <span style={{ color: getPRStateColor(prStatus.state), fontWeight: '600' }}>
                          {prStatus.state.toUpperCase()}
                        </span>
                        {prStatus.mergeable !== undefined && (
                          <span style={{ color: prStatus.mergeable ? '#86efac' : '#fca5a5', fontSize: '0.875rem', marginLeft: '0.5rem' }}>
                            {prStatus.mergeable ? '✓ Mergeable' : '✗ Conflicts'}
                          </span>
                        )}
                      </div>

                      {/* CI Checks */}
                      {prStatus.checks && prStatus.checks.length > 0 && (
                        <div>
                          <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                            CI Checks:
                          </p>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            {prStatus.checks.map((check: any, idx: number) => (
                              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem' }}>
                                <span>
                                  {check.conclusion === 'success' ? '✅' :
                                   check.conclusion === 'failure' ? '❌' :
                                   check.status === 'in_progress' ? '🔄' : '⏳'}
                                </span>
                                <span style={{ color: '#cbd5e1' }}>{check.name}</span>
                                <span style={{
                                  color: check.conclusion === 'success' ? '#86efac' :
                                         check.conclusion === 'failure' ? '#fca5a5' : '#fbbf24'
                                }}>
                                  {check.conclusion || check.status}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Overall Status */}
                      <div style={{
                        marginTop: '0.5rem',
                        padding: '0.75rem',
                        background: prStatus.all_checks_passed ? 'rgba(34, 197, 94, 0.1)' : 'rgba(251, 146, 60, 0.1)',
                        border: `1px solid ${prStatus.all_checks_passed ? '#22c55e' : '#f59e0b'}`,
                        borderRadius: '0.25rem'
                      }}>
                        <p style={{
                          color: prStatus.all_checks_passed ? '#86efac' : '#fbbf24',
                          fontSize: '0.875rem',
                          fontWeight: '600'
                        }}>
                          {prStatus.all_checks_passed ? '✅ All checks passed!' :
                           prStatus.state === 'merged' ? '✅ PR already merged!' :
                           '⏳ Waiting for checks to complete...'}
                        </p>
                      </div>

                      {/* Last Checked */}
                      <p style={{ color: '#64748b', fontSize: '0.75rem', marginTop: '0.5rem' }}>
                        Last checked: {new Date().toLocaleString()}
                      </p>
                    </div>
                  </div>
                )}

                {/* PR Status Error */}
                {prStatusError && (
                  <div style={{ marginTop: '1rem', background: 'rgba(220, 38, 38, 0.2)', border: '1px solid #dc2626', padding: '1rem', borderRadius: '0.25rem' }}>
                    <p style={{ color: '#fca5a5', fontSize: '0.875rem' }}>{prStatusError}</p>
                  </div>
                )}
              </div>
            )}

            {/* Low Confidence Warning */}
            {result.confidence < 0.5 && (
              <div style={{ background: 'rgba(251, 146, 60, 0.2)', border: '1px solid #f59e0b', padding: '1.5rem', borderRadius: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.75rem' }}>
                  <span style={{ fontSize: '1.5rem' }}>⚠️</span>
                  <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: '#fbbf24' }}>
                    Manual Review Required
                  </h3>
                </div>
                <p style={{ color: '#fde68a', fontSize: '0.875rem' }}>
                  Fix confidence is {(result.confidence * 100).toFixed(0)}% - too low for automatic PR creation.
                  Please review the analysis and create a PR manually if appropriate.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Back Link */}
        <div style={{ marginTop: '2rem', textAlign: 'center' }}>
          <a href="/" style={{ color: '#60a5fa', textDecoration: 'underline' }}>
            Analyze Another Issue
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
