# TCA RCA Agent

AI-Powered Root Cause Analysis for Sentry Issues with Automated PR Creation

## Overview

TCA (Test Coverage Agent) RCA is an intelligent system that automatically analyzes Sentry issues, determines root causes, generates fixes with tests, and creates GitHub pull requests - all powered by Claude's Agent SDK with MCP tools.

### Key Features

- **Automated RCA Analysis**: Analyzes Sentry issues using Claude Agent SDK
- **Evidence Collection**: Gathers context from SignOz, PostHog, AWS CloudWatch, and GitHub  
- **Smart Fix Generation**: Creates minimal, targeted fixes with confidence scoring
- **Test Generation**: Automatically writes unit tests for fixes
- **PR Automation**: Creates GitHub PRs with git blame for reviewer assignment
- **Learning System**: Learns from past fixes using Mem0 for pattern recognition
- **Batch Processing**: Groups similar issues for cost-efficient analysis (77% savings with prompt caching)
- **Real-time Dashboard**: Next.js dashboard with SSE streaming for live progress updates
- **Cancellation Support**: Stop stuck analyses to prevent credit waste

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Claude API key (get from https://console.anthropic.com)
- Sentry auth token
- GitHub token

### 1. Clone & Setup

```bash
git clone https://github.com/AltimateAI/tca-rca-agent.git
cd tca-rca-agent

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
```

### 2. Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start backend
python -m uvicorn tca_api.main:app --reload
```

Backend will be available at: http://localhost:8000

### 3. Dashboard Setup

```bash
cd dashboard
npm install
npm run dev
```

Dashboard will be available at: http://localhost:3001

### 4. Access the App

- **Dashboard**: http://localhost:3001
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Documentation

- **Quick Start**: See above
- **Examples**: `/examples` directory
- **Claude Code Migration**: `/examples/CLAUDE_CODE_MIGRATION_GUIDE.md`

## License

MIT License
