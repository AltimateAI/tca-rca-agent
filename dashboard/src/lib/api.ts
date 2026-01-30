import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface RCARequest {
  issue_id: string;
  sentry_org: string;
}

export interface RCAStreamEvent {
  type: 'progress' | 'result' | 'error';
  data: any;
}

export interface IssueInfo {
  line: number;
  pattern: string;
  needs_fix: boolean;
}

export interface Evidence {
  signoz_metrics?: any;
  posthog_sessions?: any;
  aws_logs?: any;
  github_context?: any;
}

export interface RCAResult {
  issue_id: string;
  sentry_url: string;
  root_cause: string;
  fix_explanation: string;
  fix_approach: string;
  file_path: string;
  function_name: string;
  same_file_issues: IssueInfo[];
  codebase_issues: string[];
  related_sentry_issues: string[];
  fix_code: string;
  test_code: string;
  confidence: number;
  analysis_time_seconds: number;
  frontend_impact: string;
  requires_approval: boolean;
  dry_run: boolean;
  learned_context: string;

  // Evidence fields
  evidence?: Evidence;
  infrastructure_correlation?: number;
  user_impact_score?: number;
}

export interface HistoryItem {
  id: string;
  issue_id: string;
  created_at: string;
  status: 'pending' | 'success' | 'failed' | 'analyzing' | 'completed';
  result?: RCAResult;
  error?: string;
}

export const api = {
  async startAnalysis(request: RCARequest): Promise<string> {
    const response = await axios.post(`${API_BASE}/api/rca/analyze`, request);
    return response.data.analysis_id;
  },

  streamAnalysis(
    analysisId: string,
    onEvent: (event: RCAStreamEvent) => void
  ): { promise: Promise<void>; close: () => void } {
    const eventSource = new EventSource(
      `${API_BASE}/api/rca/stream/${analysisId}`
    );

    const promise = new Promise<void>((resolve, reject) => {
      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        onEvent(data);

        if (data.type === 'result' || data.type === 'error') {
          eventSource.close();
          resolve();
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        reject(new Error('Stream connection failed'));
      };
    });

    return {
      promise,
      close: () => eventSource.close()
    };
  },

  async getHistory(): Promise<HistoryItem[]> {
    const response = await axios.get(`${API_BASE}/api/rca/history`);
    return response.data;
  },

  async getStats() {
    const response = await axios.get(`${API_BASE}/api/rca/stats`);
    return response.data;
  },

  async createPR(analysisId: string): Promise<{ pr_url: string; pr_number: number; branch: string; status: string }> {
    const response = await axios.post(`${API_BASE}/api/rca/${analysisId}/create-pr`);
    return response.data;
  }
};
