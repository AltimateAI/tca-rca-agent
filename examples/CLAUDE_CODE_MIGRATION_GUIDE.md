# Claude Code Migration Guide
## From Custom Backend to Claude Code CLI

### 📊 Cost Comparison

| Approach | Monthly Cost | Setup Complexity | Maintenance |
|----------|-------------|------------------|-------------|
| **Current (API-based)** | $300-500/mo | High (Backend + DB + Dashboard) | Medium-High |
| **Claude Code (Pro)** | $20/user/mo | Low (Scripts only) | Low |
| **Claude Code (Team)** | $30/user/mo | Low-Medium | Low |

**Example:**
- 100 analyses/day with API: ~$450/month
- 100 analyses/day with Claude Code: $20-30/month (included in subscription)
- **Savings: 93-95%**

### 🎯 Feature Comparison

| Feature | Your Current System | Claude Code Approach |
|---------|-------------------|---------------------|
| **RCA Analysis** | ✅ Custom FastAPI + Claude API | ✅ CLI with `-p` flag |
| **Batch Processing** | ✅ Custom grouping logic | ✅ Shell loop or parallel |
| **Prompt Caching** | ✅ Manual implementation | ✅ Automatic in Opus |
| **Dashboard** | ✅ Next.js custom UI | ❌ Slack/CLI only |
| **Learning System** | ✅ Mem0 integration | ⚠️ Manual via files |
| **Auto PR Creation** | ✅ Via API | ✅ Via MCP GitHub tool |
| **Evidence Collection** | ✅ SignOz/AWS/PostHog | ✅ Same via MCP |
| **Slack Notifications** | ✅ Custom webhook | ✅ Bot integration |
| **Queue Management** | ✅ In-memory dict | ⚠️ File-based or Redis |
| **Team Visibility** | ✅ Dashboard | ⚠️ Slack + Git history |
| **API Access** | ✅ REST endpoints | ❌ CLI only |

### 🏗️ Architecture Options

#### **Option A: Full Replacement (Minimal)**
```
┌─────────────┐
│   Cron Job  │ ──→ Scan Sentry every hour
└─────────────┘
       ↓
┌─────────────┐
│ Shell Script│ ──→ Loop through issues
└─────────────┘
       ↓
┌─────────────┐
│ Claude Code │ ──→ Analysis + PR creation
│  (Opus CLI) │
└─────────────┘
       ↓
┌─────────────┐
│    Slack    │ ──→ Notify team
└─────────────┘
```

**Pros:**
- ✅ 95% cost reduction
- ✅ No backend maintenance
- ✅ Uses Claude Pro/Team subscription
- ✅ Access to Opus model

**Cons:**
- ❌ No web dashboard
- ❌ Manual queue management
- ❌ Limited team visibility

#### **Option B: Hybrid (Recommended)**
```
┌──────────────────────────────────────────┐
│         Lightweight API Server           │
│  (Just for queueing + Slack webhooks)    │
└──────────────────────────────────────────┘
           ↓                    ↑
    Queue Issues         Get Results
           ↓                    ↑
┌──────────────────────────────────────────┐
│         Background Workers               │
│   (Node.js or Python calling Claude CLI) │
└──────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────┐
│         Claude Code CLI (Opus)           │
│  (All analysis happens here)             │
└──────────────────────────────────────────┘
           ↓
  ┌────────────────┐
  │  GitHub PRs    │
  │  Slack Alerts  │
  └────────────────┘
```

**Pros:**
- ✅ 90% cost reduction (small server cost)
- ✅ Team visibility via Slack
- ✅ Async processing
- ✅ Easy to scale workers

**Cons:**
- ⚠️ Still need to maintain small backend
- ⚠️ No fancy dashboard (but Slack works)

#### **Option C: Slack-First (Modern)**
```
      Slack Slash Commands
              ↓
    ┌─────────────────────┐
    │   Slack Bot Server  │
    │  (Bolt.js or Flask) │
    └─────────────────────┘
              ↓
    ┌─────────────────────┐
    │   Claude Code CLI   │
    │   (spawned per cmd) │
    └─────────────────────┘
              ↓
    ┌─────────────────────┐
    │  Interactive Cards  │
    │  in Slack Threads   │
    └─────────────────────┘
```

**Example Workflow:**
```
User: /fix-sentry 7088840785
Bot:  🔄 Analyzing issue...
      [5 seconds later]
      ✅ Root cause: KeyError in user_email()
      📝 Created PR #456
      [View PR] [Approve & Merge]
```

**Pros:**
- ✅ Best UX for teams
- ✅ No separate dashboard needed
- ✅ Slack is already where teams are
- ✅ Interactive buttons for approval

**Cons:**
- ⚠️ Requires Slack app setup

### 🚀 Quick Start: Shell Script Approach

#### 1. **Install Claude Code**
```bash
npm install -g @anthropic/claude-code
claude auth login
```

#### 2. **Add Sentry MCP Server**
```bash
claude mcp add --transport http sentry https://mcp.sentry.dev/mcp
```

#### 3. **Set Environment Variables**
```bash
export SENTRY_ORG="altimate-inc"
export SENTRY_AUTH_TOKEN="your_token"
export GITHUB_REPO="altimate-inc/altimate-backend"
export SLACK_WEBHOOK="https://hooks.slack.com/..."
```

#### 4. **Run the Auto-Fix Script**
```bash
chmod +x examples/sentry-autofix.sh
./examples/sentry-autofix.sh
```

#### 5. **Schedule with Cron**
```bash
# Add to crontab (every hour)
0 * * * * /path/to/sentry-autofix.sh >> /var/log/sentry-autofix.log 2>&1
```

### 🔧 Advanced: Slack Bot Setup

#### 1. **Create Slack App**
- Go to https://api.slack.com/apps
- Click "Create New App"
- Enable Socket Mode
- Add slash commands:
  - `/fix-sentry` - Fix a specific issue
  - `/analyze-recent-errors` - Scan all recent errors

#### 2. **Install Dependencies**
```bash
cd examples
npm init -y
npm install @slack/bolt
```

#### 3. **Set Environment Variables**
```bash
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_SIGNING_SECRET="..."
export SLACK_APP_TOKEN="xapp-..."
export SENTRY_ORG="altimate-inc"
export SENTRY_AUTH_TOKEN="..."
```

#### 4. **Run the Bot**
```bash
node slack-claude-bot.js
```

#### 5. **Deploy to Production**
```bash
# Option 1: PM2
npm install -g pm2
pm2 start slack-claude-bot.js --name sentry-bot
pm2 save
pm2 startup

# Option 2: Docker
docker build -t sentry-bot .
docker run -d --env-file .env sentry-bot

# Option 3: Fly.io
fly launch
fly deploy
```

### 💡 Key Learnings to Keep

From your current system, keep these valuable patterns:

#### 1. **Issue Grouping**
```bash
# Instead of processing individually, group by error type
claude -p "Analyze these 5 KeyError issues together and find common patterns: ..."
```

#### 2. **Priority Scoring**
```bash
# Use Claude to calculate smart priorities
claude -p "Score these issues (0-100) based on frequency, users, and infrastructure correlation"
```

#### 3. **Evidence Collection**
```bash
# Still use your MCP tools
claude -p "Before analyzing, gather evidence from SignOz, AWS CloudWatch, and PostHog"
```

#### 4. **Learning Loop**
```bash
# Store patterns in a JSON file instead of Mem0
mkdir -p ~/.sentry-patterns
echo '{"KeyError": ["Always check dict.get()", ...]}' > ~/.sentry-patterns/patterns.json

# Then inject into Claude prompts
claude -p "Using these learned patterns: $(cat ~/.sentry-patterns/patterns.json), analyze..."
```

### 📈 Migration Path

**Week 1: Proof of Concept**
- [ ] Set up Claude Code CLI
- [ ] Test shell script with 1-2 issues
- [ ] Verify MCP tools work (Sentry, GitHub)
- [ ] Compare results with current system

**Week 2: Slack Integration**
- [ ] Create Slack app
- [ ] Implement `/fix-sentry` command
- [ ] Test with team
- [ ] Gather feedback

**Week 3: Automation**
- [ ] Set up cron job for scheduled scans
- [ ] Implement batch processing
- [ ] Add error handling and retries
- [ ] Monitor cost savings

**Week 4: Sunset Old System**
- [ ] Export historical data
- [ ] Migrate learned patterns to files
- [ ] Redirect users to Slack bot
- [ ] Decommission old backend

### 🎓 Resources

**Official Documentation:**
- [Claude Code Docs](https://code.claude.com/docs)
- [Headless Mode](https://code.claude.com/docs/en/headless)
- [Sentry MCP Server](https://docs.sentry.io/product/sentry-mcp/)

**Community Examples:**
- [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) - 200+ skills and examples
- [claude-code-slack-bot](https://github.com/mpociot/claude-code-slack-bot) - Reference implementation
- [claude-autofix-bot](https://github.com/MattKilmer/claude-autofix-bot) - Similar to your use case

**Cost Optimization:**
- Use Sonnet for simple fixes (faster, cheaper)
- Use Opus for complex root cause analysis
- Batch similar issues together for prompt caching

### ❓ FAQ

**Q: Can I still use Mem0 for learning?**
A: Not directly with CLI. Alternative: Store patterns in JSON files and inject into prompts.

**Q: What about the dashboard?**
A: Slack becomes your dashboard. Use rich message formatting, buttons, and threads.

**Q: Can multiple team members use this?**
A: Yes! Each person needs Claude Pro/Team subscription. Or run as a shared bot with one subscription.

**Q: What about rate limits?**
A: Claude Code has higher rate limits than API. Team plan gets even higher limits.

**Q: Can I use this in CI/CD?**
A: Yes! The `-p` flag works in GitHub Actions, GitLab CI, etc.

**Q: What happens if Claude Code is down?**
A: Fallback to API-based system or queue issues for later processing.

### 🎯 Recommendation

Based on your requirements:

**Start with Option C (Slack-First):**
1. 95% cost reduction vs current system
2. Better UX than web dashboard (team is already in Slack)
3. Easy to add features via slash commands
4. Can still do batch processing in background
5. Access to Opus for hard problems

**Timeline:** 2-3 weeks to fully migrate

**ROI:** $400-450/month savings, -50% maintenance burden
