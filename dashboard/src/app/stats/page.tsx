'use client';

import { useEffect, useState } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Stats {
  total_patterns: number;
  total_antipatterns: number;
  high_confidence_patterns: number;
  total_memories: number;
  mode: string | null;
}

interface BootstrapStatus {
  last_bootstrap: string | null;
  patterns_loaded: number;
  projects: string[];
  needs_bootstrap: boolean;
  months_since_last: number | null;
}

export default function StatsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [bootstrapStatus, setBootstrapStatus] = useState<BootstrapStatus | null>(null);
  const [bootstrapping, setBootstrapping] = useState(false);
  const [bootstrapMessage, setBootstrapMessage] = useState<string | null>(null);

  useEffect(() => {
    loadStats();
    loadBootstrapStatus();
    // Refresh every 30 seconds
    const interval = setInterval(() => {
      loadStats();
      loadBootstrapStatus();
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadStats = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/rca/stats`);
      if (!response.ok) throw new Error('Failed to load stats');
      const data = await response.json();
      setStats(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadBootstrapStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/discovery/bootstrap/status`);
      if (!response.ok) throw new Error('Failed to load bootstrap status');
      const data = await response.json();
      setBootstrapStatus(data);
    } catch (err: any) {
      console.error('Failed to load bootstrap status:', err);
    }
  };

  const triggerBootstrap = async () => {
    setBootstrapping(true);
    setBootstrapMessage(null);

    try {
      const response = await fetch(`${API_BASE}/api/discovery/bootstrap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projects: ['altimate-backend', 'altimate-frontend', 'freemium-backend'],
          max_issues_per_project: 50,
          min_occurrences: 20,
          months_back: 6
        })
      });

      if (!response.ok) throw new Error('Failed to start bootstrap');

      const data = await response.json();

      if (data.status === 'skipped') {
        setBootstrapMessage(`⏭️ ${data.message}`);
      } else {
        setBootstrapMessage(`🚀 ${data.message}`);
        // Refresh stats after 3 minutes
        setTimeout(() => {
          loadStats();
          loadBootstrapStatus();
        }, 180000);
      }
    } catch (err: any) {
      setBootstrapMessage(`❌ Error: ${err.message}`);
    } finally {
      setBootstrapping(false);
    }
  };

  const getSuccessRate = () => {
    if (!stats) return 0;
    const total = stats.total_patterns + stats.total_antipatterns;
    if (total === 0) return 0;
    return (stats.total_patterns / total) * 100;
  };

  const getLearningStatus = () => {
    if (!stats) return { status: 'Unknown', color: '#64748b', icon: '❓' };

    if (stats.total_patterns === 0 && stats.total_antipatterns === 0) {
      return { status: 'Not Learning', color: '#dc2626', icon: '⚠️' };
    }

    if (stats.total_patterns >= 10) {
      return { status: 'Learning Well', color: '#22c55e', icon: '✅' };
    }

    return { status: 'Learning Started', color: '#f59e0b', icon: '🔄' };
  };

  const learningStatus = getLearningStatus();
  const successRate = getSuccessRate();

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(to bottom right, #0f172a, #1e293b, #0f172a)', padding: '2rem' }}>
      <div style={{ maxWidth: '80rem', margin: '0 auto' }}>
        <h1 style={{ fontSize: '1.875rem', fontWeight: 'bold', color: 'white', marginBottom: '2rem' }}>
          📊 RCA Agent Learning Stats
        </h1>

        {/* Learning Status */}
        <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155', marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ fontSize: '3rem' }}>{learningStatus.icon}</div>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: '600', color: learningStatus.color, marginBottom: '0.25rem' }}>
                {learningStatus.status}
              </h2>
              <p style={{ color: '#94a3b8', fontSize: '0.875rem' }}>
                {stats && stats.total_patterns === 0 && stats.total_antipatterns === 0
                  ? 'Agent has not learned any patterns yet. Create and merge PRs to start learning.'
                  : `Agent has learned from ${stats?.total_patterns || 0} successful PRs`}
              </p>
            </div>
            <button
              onClick={loadStats}
              disabled={loading}
              style={{
                marginLeft: 'auto',
                background: '#334155',
                color: 'white',
                padding: '0.5rem 1rem',
                borderRadius: '0.25rem',
                border: '1px solid #475569',
                fontSize: '0.875rem',
                fontWeight: '600',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.5 : 1
              }}
            >
              {loading ? '🔄 Refreshing...' : '🔄 Refresh'}
            </button>
          </div>
        </div>

        {error && (
          <div style={{ background: 'rgba(220, 38, 38, 0.2)', border: '1px solid #dc2626', padding: '1rem', borderRadius: '0.25rem', marginBottom: '2rem' }}>
            <p style={{ color: '#fca5a5', fontSize: '0.875rem' }}>{error}</p>
          </div>
        )}

        {/* Stats Grid */}
        {stats && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
              {/* Total Patterns */}
              <div style={{ background: 'rgba(34, 197, 94, 0.2)', border: '1px solid #22c55e', padding: '1.5rem', borderRadius: '0.5rem' }}>
                <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>✅</div>
                <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#86efac', marginBottom: '0.5rem' }}>
                  {stats.total_patterns}
                </div>
                <div style={{ color: '#bbf7d0', fontSize: '0.875rem' }}>
                  Successful Patterns
                </div>
                <div style={{ color: '#86efac', fontSize: '0.75rem', marginTop: '0.25rem' }}>
                  PRs merged successfully
                </div>
              </div>

              {/* Anti-patterns */}
              <div style={{ background: 'rgba(239, 68, 68, 0.2)', border: '1px solid #ef4444', padding: '1.5rem', borderRadius: '0.5rem' }}>
                <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>❌</div>
                <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#fca5a5', marginBottom: '0.5rem' }}>
                  {stats.total_antipatterns}
                </div>
                <div style={{ color: '#fecaca', fontSize: '0.875rem' }}>
                  Anti-Patterns
                </div>
                <div style={{ color: '#fca5a5', fontSize: '0.75rem', marginTop: '0.25rem' }}>
                  PRs rejected or reverted
                </div>
              </div>

              {/* High Confidence */}
              <div style={{ background: 'rgba(59, 130, 246, 0.2)', border: '1px solid #3b82f6', padding: '1.5rem', borderRadius: '0.5rem' }}>
                <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>⭐</div>
                <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#93c5fd', marginBottom: '0.5rem' }}>
                  {stats.high_confidence_patterns}
                </div>
                <div style={{ color: '#bfdbfe', fontSize: '0.875rem' }}>
                  High Confidence
                </div>
                <div style={{ color: '#93c5fd', fontSize: '0.75rem', marginTop: '0.25rem' }}>
                  Patterns with 90%+ confidence
                </div>
              </div>

              {/* Total Memories */}
              <div style={{ background: 'rgba(168, 85, 247, 0.2)', border: '1px solid #a855f7', padding: '1.5rem', borderRadius: '0.5rem' }}>
                <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🧠</div>
                <div style={{ fontSize: '2.5rem', fontWeight: 'bold', color: '#d8b4fe', marginBottom: '0.5rem' }}>
                  {stats.total_memories}
                </div>
                <div style={{ color: '#e9d5ff', fontSize: '0.875rem' }}>
                  Total Memories
                </div>
                <div style={{ color: '#d8b4fe', fontSize: '0.75rem', marginTop: '0.25rem' }}>
                  Stored in Mem0
                </div>
              </div>
            </div>

            {/* Success Rate */}
            {(stats.total_patterns > 0 || stats.total_antipatterns > 0) && (
              <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155', marginBottom: '2rem' }}>
                <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'white', marginBottom: '1rem' }}>
                  Success Rate
                </h3>
                <div style={{ background: '#0f172a', borderRadius: '9999px', height: '2rem', overflow: 'hidden', position: 'relative' }}>
                  <div
                    style={{
                      background: successRate >= 80 ? '#22c55e' : successRate >= 60 ? '#f59e0b' : '#dc2626',
                      width: `${successRate}%`,
                      height: '100%',
                      transition: 'width 0.5s ease'
                    }}
                  />
                  <div style={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    color: 'white',
                    fontWeight: '600',
                    fontSize: '0.875rem'
                  }}>
                    {successRate.toFixed(1)}%
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem', fontSize: '0.75rem', color: '#94a3b8' }}>
                  <span>{stats.total_patterns} successful</span>
                  <span>{stats.total_antipatterns} failed</span>
                </div>
              </div>
            )}

            {/* Mode Info */}
            <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
              <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'white', marginBottom: '1rem' }}>
                Learning Mode
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <div style={{
                  background: stats.mode ? '#22c55e' : '#dc2626',
                  width: '0.75rem',
                  height: '0.75rem',
                  borderRadius: '50%'
                }} />
                <span style={{ color: '#cbd5e1' }}>
                  {stats.mode || 'Not configured'}
                </span>
              </div>

              {stats.total_patterns === 0 && stats.total_antipatterns === 0 && (
                <>
                  <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(59, 130, 246, 0.1)', border: '1px solid #3b82f6', borderRadius: '0.25rem' }}>
                    <h4 style={{ color: '#93c5fd', fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.5rem' }}>
                      💡 How to Start Learning
                    </h4>
                    <ol style={{ color: '#bfdbfe', fontSize: '0.75rem', paddingLeft: '1.25rem', lineHeight: '1.6' }}>
                      <li>Analyze a Sentry issue</li>
                      <li>Create a PR with the "Create Pull Request" button</li>
                      <li>Merge the PR on GitHub</li>
                      <li>GitHub webhook will notify the agent</li>
                      <li>Agent stores the successful pattern in Mem0</li>
                      <li>Future similar issues will use this pattern</li>
                    </ol>
                  </div>

                  {/* Bootstrap Section */}
                  <div style={{ marginTop: '1rem', padding: '1rem', background: 'rgba(34, 197, 94, 0.1)', border: '1px solid #22c55e', borderRadius: '0.25rem' }}>
                    <h4 style={{ color: '#86efac', fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.5rem' }}>
                      🌱 Bootstrap from Historical Data
                    </h4>
                    <p style={{ color: '#bbf7d0', fontSize: '0.75rem', lineHeight: '1.6', marginBottom: '0.75rem' }}>
                      Get a head start by loading patterns from previously resolved Sentry issues. This will analyze ~50 issues per project that have already been fixed in production.
                    </p>

                    {bootstrapStatus && !bootstrapStatus.needs_bootstrap && (
                      <div style={{ color: '#86efac', fontSize: '0.75rem', marginBottom: '0.75rem', padding: '0.5rem', background: 'rgba(34, 197, 94, 0.1)', borderRadius: '0.25rem' }}>
                        ✅ Last bootstrap: {new Date(bootstrapStatus.last_bootstrap!).toLocaleDateString()} ({bootstrapStatus.months_since_last?.toFixed(1)} months ago)
                        <br />
                        📊 {bootstrapStatus.patterns_loaded} patterns loaded from {bootstrapStatus.projects.length} projects
                      </div>
                    )}

                    <button
                      onClick={triggerBootstrap}
                      disabled={bootstrapping || (bootstrapStatus !== null && !bootstrapStatus.needs_bootstrap)}
                      style={{
                        background: bootstrapStatus?.needs_bootstrap !== false ? '#22c55e' : '#334155',
                        color: 'white',
                        padding: '0.5rem 1rem',
                        borderRadius: '0.25rem',
                        border: 'none',
                        fontSize: '0.75rem',
                        fontWeight: '600',
                        cursor: (bootstrapping || (bootstrapStatus !== null && !bootstrapStatus.needs_bootstrap)) ? 'not-allowed' : 'pointer',
                        opacity: (bootstrapping || (bootstrapStatus !== null && !bootstrapStatus.needs_bootstrap)) ? 0.5 : 1,
                        width: '100%'
                      }}
                    >
                      {bootstrapping ? '⏳ Loading Historical Patterns...' :
                       bootstrapStatus?.needs_bootstrap !== false ? '🚀 Load Historical Patterns' :
                       '✅ Already Bootstrapped'}
                    </button>

                    {bootstrapMessage && (
                      <div style={{
                        marginTop: '0.75rem',
                        padding: '0.5rem',
                        background: 'rgba(168, 85, 247, 0.1)',
                        border: '1px solid #a855f7',
                        borderRadius: '0.25rem',
                        color: '#d8b4fe',
                        fontSize: '0.75rem'
                      }}>
                        {bootstrapMessage}
                      </div>
                    )}

                    <div style={{ marginTop: '0.75rem', color: '#86efac', fontSize: '0.625rem', lineHeight: '1.4' }}>
                      <div>📌 Projects: altimate-backend, altimate-frontend, freemium-backend</div>
                      <div>📊 ~50 issues per project</div>
                      <div>⏰ Takes 2-3 minutes</div>
                      <div>🔄 Runs once every 6 months</div>
                    </div>
                  </div>
                </>
              )}
            </div>
          </>
        )}

        {/* Back Link */}
        <div style={{ marginTop: '2rem', textAlign: 'center' }}>
          <a href="/" style={{ color: '#60a5fa', textDecoration: 'underline' }}>
            ← Back to Home
          </a>
        </div>
      </div>
    </div>
  );
}
