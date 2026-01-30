'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '../lib/api';

export default function HomePage() {
  const router = useRouter();
  const [issueId, setIssueId] = useState('');
  const [sentryOrg, setSentryOrg] = useState('altimate-inc');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const analysisId = await api.startAnalysis({
        issue_id: issueId,
        sentry_org: sentryOrg
      });

      router.push(`/analyze/${analysisId}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start analysis');
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(to bottom right, #0f172a, #1e293b, #0f172a)', padding: '2rem' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '4rem' }}>
          <h1 style={{ fontSize: '3.75rem', fontWeight: 'bold', color: 'white', marginBottom: '1rem' }}>
            TCA RCA Agent
          </h1>
          <p style={{ fontSize: '1.25rem', color: '#cbd5e1' }}>
            AI-Powered Root Cause Analysis & Automated Fixes
          </p>
        </div>

        {/* Features */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem', marginBottom: '4rem' }}>
          <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🧠</div>
            <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'white', marginBottom: '0.5rem' }}>
              Smart Analysis
            </h3>
            <p style={{ color: '#94a3b8' }}>
              Claude analyzes stack traces and generates root cause explanations
            </p>
          </div>

          <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>⚡</div>
            <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'white', marginBottom: '0.5rem' }}>
              Self-Learning
            </h3>
            <p style={{ color: '#94a3b8' }}>
              Learns from PR outcomes to improve fix quality over time
            </p>
          </div>

          <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155' }}>
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🔀</div>
            <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'white', marginBottom: '0.5rem' }}>
              Auto PR Creation
            </h3>
            <p style={{ color: '#94a3b8' }}>
              Creates GitHub PRs with fixes and test cases automatically
            </p>
          </div>
        </div>

        {/* Input Form */}
        <div style={{ maxWidth: '48rem', margin: '0 auto' }}>
          <div style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '2rem', borderRadius: '0.75rem', border: '1px solid #334155' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: '600', color: 'white', marginBottom: '1.5rem' }}>
              Analyze Sentry Issue
            </h2>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#cbd5e1', marginBottom: '0.5rem' }}>
                  Sentry Issue ID
                </label>
                <input
                  type="text"
                  value={issueId}
                  onChange={(e) => setIssueId(e.target.value)}
                  placeholder="e.g., 1234567890"
                  style={{ width: '100%', padding: '0.75rem 1rem', background: '#0f172a', border: '1px solid #475569', borderRadius: '0.5rem', color: 'white', outline: 'none' }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#cbd5e1', marginBottom: '0.5rem' }}>
                  Sentry Organization
                </label>
                <input
                  type="text"
                  value={sentryOrg}
                  onChange={(e) => setSentryOrg(e.target.value)}
                  placeholder="e.g., altimate-inc"
                  style={{ width: '100%', padding: '0.75rem 1rem', background: '#0f172a', border: '1px solid #475569', borderRadius: '0.5rem', color: 'white', outline: 'none' }}
                  required
                />
              </div>

              {error && (
                <div style={{ padding: '1rem', background: 'rgba(220, 38, 38, 0.2)', border: '1px solid #dc2626', borderRadius: '0.5rem', color: '#fca5a5' }}>
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                style={{ width: '100%', padding: '0.75rem 1.5rem', background: loading ? '#475569' : '#3b82f6', color: 'white', fontWeight: '600', borderRadius: '0.5rem', border: 'none', cursor: loading ? 'not-allowed' : 'pointer', transition: 'background 0.2s' }}
              >
                {loading ? 'Starting Analysis...' : 'Start Analysis →'}
              </button>
            </form>
          </div>

          <div style={{ textAlign: 'center', marginTop: '2rem' }}>
            <div style={{ display: 'flex', gap: '2rem', justifyContent: 'center', flexWrap: 'wrap' }}>
              <a
                href="/scan"
                style={{ color: '#60a5fa', textDecoration: 'underline' }}
              >
                🔍 Scan Sentry for Issues
              </a>
              <a
                href="/history"
                style={{ color: '#60a5fa', textDecoration: 'underline' }}
              >
                📋 View Analysis History
              </a>
              <a
                href="/stats"
                style={{ color: '#60a5fa', textDecoration: 'underline' }}
              >
                📊 Learning Stats
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
