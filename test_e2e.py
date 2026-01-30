import asyncio
from tca_core.rca_agent import RCAAgent
from tca_core.memory_system import MemorySystem

async def test():
    print("🧪 Testing RCA Agent End-to-End\n")

    agent = RCAAgent(memory_system=MemorySystem())

    # Use a real Sentry issue ID
    issue_id = "5849464050"  # Replace with actual issue ID if needed

    print(f"Analyzing issue {issue_id}...\n")

    async for event in agent.analyze_issue(issue_id):
        if event["type"] == "status":
            print(f"📊 {event['message']}")
        elif event["type"] == "thinking":
            print(f"💭 {event['content'][:100]}...")
        elif event["type"] == "complete":
            result = event["result"]
            print(f"\n✅ ANALYSIS COMPLETE")
            print(f"   Error Type: {result.get('error_type')}")
            print(f"   File: {result.get('file_path')}")
            print(f"   Function: {result.get('function_name')}")
            root_cause = result.get('root_cause', '')
            if root_cause:
                print(f"   Root Cause: {root_cause[:150]}...")
            print(f"   Confidence: {result.get('fix_confidence', 0):.0%}")
            fix_code = result.get('fix_code')
            if fix_code:
                print(f"   Fix Code: {len(fix_code)} chars")
            print(f"   Can Auto-Fix: {result.get('can_auto_fix')}")
        elif event["type"] == "error":
            print(f"\n❌ ERROR: {event['message']}")

if __name__ == "__main__":
    asyncio.run(test())
