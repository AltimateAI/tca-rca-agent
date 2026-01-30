# TCA RCA Agent - Quick Start Guide

**Status**: ✅ All phases complete and verified

## 🎉 What Was Built

✅ **Phase 1**: Core RCA Engine with DRY_RUN support
✅ **Phase 2**: Learning System with Mem0 integration (mock mode ready)
✅ **Phase 3**: FastAPI backend with SSE streaming
✅ **Phase 4**: Next.js dashboard with real-time updates
✅ **Phase 5**: Documentation and verification scripts

## 🚀 Start Using Now (3 Commands)

### 1. Start the API Server (Terminal 1)

```bash
cd ~/git/tca-latest
python3 -m uvicorn tca_api.main:app --reload --port 8000
```

You should see:
```
✅ Server started successfully
   API docs: http://localhost:8000/docs
   Health check: http://localhost:8000/health
```

### 2. Install Dashboard Dependencies & Start (Terminal 2)

```bash
cd ~/git/tca-latest/dashboard
npm install   # First time only, takes 1-2 minutes
npm run dev
```

You should see:
```
✓ Ready in 2.3s
○ Local:   http://localhost:3000
```

### 3. Open Dashboard

Open http://localhost:3000 in your browser.

## 🎯 Test the System (DRY_RUN Mode)

**No Anthropic API calls needed! Everything works with mock data.**

1. **Home Page** (http://localhost:3000)
   - Enter issue ID: `test-123`
   - Organization: `altimate-inc`
   - Click "Start Analysis"

2. **Watch Real-Time Progress**
   - You'll be redirected to /analyze/{id}
   - Progress streams in real-time (10 phases)
   - Shows: "Gathering bug information", "Analyzing stack trace", etc.

3. **View Results**
   - Root cause explanation
   - Fix code (Python with proper null checks)
   - Test code (pytest test cases)
   - Confidence score: 85%

4. **Check History**
   - Click "View Analysis History"
   - See all past analyses with status

## 📊 What You'll See

### API Endpoints Available

- `GET /health` - Health check
- `POST /api/rca/analyze` - Start analysis
- `GET /api/rca/stream/{id}` - Stream progress (SSE)
- `GET /api/rca/history` - Get history
- `GET /api/rca/stats` - Learning stats
- `GET /docs` - Interactive API docs

### Dashboard Pages

- `/` - Home with input form
- `/analyze/{id}` - Real-time analysis view
- `/history` - Past analyses

## 🔧 When Ready for Real API Calls

1. **Get Anthropic Credits**
   - Add credits to your Anthropic account
   - API key is already in .env

2. **Disable DRY_RUN Mode**
   ```bash
   cd ~/git/tca-latest
   # Edit .env and remove this line:
   # TCA_DRY_RUN=true
   ```

3. **Optional: Create Mem0 Account**
   ```bash
   # Visit https://app.mem0.ai
   # Get API key
   # Add to .env:
   # MEM0_API_KEY=your_key_here
   ```

4. **Test with Real Sentry Issue**
   - Get issue ID from https://sentry.io
   - Submit in dashboard
   - Watch real Claude analysis!

## 📁 Project Structure Reference

```
~/git/tca-latest/
├── tca_core/          # ✅ Phase 1 & 2
│   ├── config.py
│   ├── code_merger.py
│   ├── memory_system.py
│   └── rca_agent.py
├── tca_api/           # ✅ Phase 3
│   ├── main.py
│   ├── models.py
│   └── routes/
├── dashboard/         # ✅ Phase 4
│   └── src/
│       ├── app/
│       └── lib/
├── .env               # ✅ Your existing credentials
└── README.md          # ✅ Full documentation
```

## 🧪 Verify Everything Works

```bash
cd ~/git/tca-latest
./scripts/verify_build.sh
```

Should show all green checkmarks (✅)

## 🐛 Quick Troubleshooting

**"Port 8000 already in use"**
```bash
# Use different port
python3 -m uvicorn tca_api.main:app --port 8001

# Update dashboard/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8001
```

**"Dashboard won't load"**
```bash
cd ~/git/tca-latest/dashboard
rm -rf node_modules .next
npm install
npm run dev
```

**"Can't see analysis results"**
- Check API is running: http://localhost:8000/health
- Check browser console for errors (F12)
- Verify .env has `TCA_DRY_RUN=true`

## 📖 Next Steps

1. **Review Documentation**
   - `TECH_ARCHITECTURE_PROPOSAL.md` - For leadership review
   - `TCA_MASTER_SPEC.md` - Complete implementation spec
   - `SETUP_INSTRUCTIONS.md` - Detailed setup guide

2. **Present to Team**
   - Use TECH_ARCHITECTURE_PROPOSAL.md
   - Show live demo at http://localhost:3000
   - Highlight: 1,700× ROI, $3/month cost

3. **Deploy to Staging**
   - Follow deployment section in README.md
   - Test with real Sentry issues
   - Validate learning loop with real PRs

## ✅ Success Criteria Met

- ✅ Uses existing .env credentials (no new setup)
- ✅ Works without API calls (DRY_RUN mode)
- ✅ Follows fix-sentry-bug.md workflow
- ✅ No placeholders (all working code)
- ✅ Real-time dashboard updates
- ✅ Complete documentation

## 🎊 You're Ready!

Everything is built and tested. Just run the 2 commands above and open the dashboard.

**Congratulations on getting approval! 🎉**

---

**Questions?** Check README.md or SETUP_INSTRUCTIONS.md for details.
