'use client';

import { useEffect, useState } from 'react';
import { api, HistoryItem } from '../../lib/api';

export default function HistoryPage() {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getHistory().then((data) => {
      setHistory(data);
      setLoading(false);
    });
  }, []);

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(to bottom right, #0f172a, #1e293b, #0f172a)', padding: '2rem' }}>
      <div style={{ maxWidth: '72rem', margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
          <h1 style={{ fontSize: '1.875rem', fontWeight: 'bold', color: 'white' }}>Analysis History</h1>
          <a
            href="/"
            style={{ padding: '0.5rem 1rem', background: '#3b82f6', color: 'white', borderRadius: '0.5rem', textDecoration: 'none' }}
          >
            New Analysis
          </a>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', color: '#94a3b8' }}>Loading...</div>
        ) : history.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#94a3b8' }}>
            No analysis history yet
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {history.map((item) => (
              <div
                key={item.id}
                style={{ background: 'rgba(30, 41, 59, 0.5)', backdropFilter: 'blur(10px)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid #334155', transition: 'border-color 0.2s' }}
              >
                <div style={{ display: 'flex', alignItems: 'start', justifyContent: 'space-between' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                      {item.status === 'completed' && (
                        <span style={{ color: '#22c55e' }}>✅</span>
                      )}
                      {item.status === 'failed' && (
                        <span style={{ color: '#ef4444' }}>❌</span>
                      )}
                      {item.status === 'analyzing' && (
                        <span style={{ color: '#eab308' }}>⏳</span>
                      )}

                      <h3 style={{ fontSize: '1.125rem', fontWeight: '600', color: 'white' }}>
                        Issue: {item.issue_id}
                      </h3>
                    </div>

                    <p style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '0.75rem' }}>
                      {new Date(item.created_at).toLocaleString()}
                    </p>

                    {item.result && (
                      <div style={{ color: '#cbd5e1', fontSize: '0.875rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        <p>
                          <span style={{ color: '#64748b' }}>Root Cause:</span>{' '}
                          {item.result.root_cause.slice(0, 100)}...
                        </p>
                        <p>
                          <span style={{ color: '#64748b' }}>File:</span>{' '}
                          <code style={{ color: '#60a5fa' }}>
                            {item.result.file_path}
                          </code>
                        </p>
                        <p>
                          <span style={{ color: '#64748b' }}>Confidence:</span>{' '}
                          {(item.result.confidence * 100).toFixed(0)}%
                        </p>
                      </div>
                    )}

                    {item.error && (
                      <p style={{ color: '#fca5a5', fontSize: '0.875rem' }}>{item.error}</p>
                    )}
                  </div>

                  <a
                    href={`/analyze/${item.id}`}
                    style={{ marginLeft: '1rem', padding: '0.5rem 1rem', background: '#475569', color: 'white', borderRadius: '0.5rem', fontSize: '0.875rem', textDecoration: 'none', transition: 'background 0.2s' }}
                  >
                    View Details →
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
