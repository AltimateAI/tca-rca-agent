"""
TCA RCA Agent Configuration
"""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()


def get_env(key: str, fallback_key: str = None) -> str:
    """Get env var with fallback to TCA_ prefixed version."""
    value = os.getenv(key)
    if not value and fallback_key:
        value = os.getenv(fallback_key)
    return value or ""


# Core Configuration
ANTHROPIC_API_KEY = get_env("ANTHROPIC_API_KEY", "TCA_ANTHROPIC_API_KEY")
SENTRY_AUTH_TOKEN = get_env("SENTRY_AUTH_TOKEN", "TCA_SENTRY_AUTH_TOKEN")
SENTRY_ORG = get_env("SENTRY_ORG", "TCA_SENTRY_ORG")
SENTRY_PROJECT = get_env("SENTRY_PROJECT", "TCA_SENTRY_PROJECT")
GITHUB_TOKEN = get_env("GITHUB_TOKEN", "TCA_GITHUB_TOKEN")
GITHUB_OWNER = get_env("GITHUB_OWNER")
GITHUB_REPO = get_env("GITHUB_REPO")
MEM0_API_KEY = get_env("MEM0_API_KEY")
MEM0_ORG_ID = get_env("MEM0_ORG_ID")
MEM0_PROJECT_ID = get_env("MEM0_PROJECT_ID")

# SignOz Configuration
SIGNOZ_HOST = get_env("SIGNOZ_HOST")
SIGNOZ_API_KEY = get_env("SIGNOZ_READONLY_API_KEY")

# PostHog Configuration
POSTHOG_PROJECT_ID = get_env("TCA_POSTHOG_PROJECT_ID")
POSTHOG_API_KEY = get_env("TCA_POSTHOG_API_KEY")
POSTHOG_HOST = get_env("TCA_POSTHOG_HOST")

# Model Configuration
MODEL_NAME = get_env("TCA_MODEL_NAME", "claude-sonnet-4-20250514")

# MCP Server Configurations
MCP_SERVERS = {
    "sentry": {
        "command": "npx",
        "args": [
            "@sentry/mcp-server",
            f"--organization-slug={SENTRY_ORG}",
        ],
        "env": {
            "SENTRY_ACCESS_TOKEN": SENTRY_AUTH_TOKEN,
        },
    },
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {
            "GITHUB_PERSONAL_ACCESS_TOKEN": GITHUB_TOKEN,
        },
    },
}

# Add SignOz MCP if configured
if SIGNOZ_HOST and SIGNOZ_API_KEY:
    MCP_SERVERS["signoz"] = {
        "command": "npx",
        "args": ["-y", "@signoz/mcp-server"],
        "env": {
            "SIGNOZ_HOST": SIGNOZ_HOST,
            "SIGNOZ_API_KEY": SIGNOZ_API_KEY,
        },
    }

# Add PostHog MCP if configured (custom server)
if POSTHOG_API_KEY and POSTHOG_PROJECT_ID:
    MCP_SERVERS["posthog"] = {
        "command": "node",
        "args": [os.path.join(os.path.dirname(__file__), "../mcp_servers/posthog_server.js")],
        "env": {
            "POSTHOG_HOST": POSTHOG_HOST,
            "POSTHOG_API_KEY": POSTHOG_API_KEY,
            "POSTHOG_PROJECT_ID": POSTHOG_PROJECT_ID,
        },
    }

# Add AWS MCP if AWS credentials are configured (custom server)
AWS_REGION = get_env("AWS_REGION")
if AWS_REGION or os.getenv("AWS_ACCESS_KEY_ID"):
    MCP_SERVERS["aws"] = {
        "command": "node",
        "args": [os.path.join(os.path.dirname(__file__), "../mcp_servers/aws_server.js")],
        "env": {
            "AWS_REGION": AWS_REGION or "us-east-1",
            "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID", ""),
            "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        },
    }


def validate_env():
    """Validate required environment variables."""
    required = {
        "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
        "SENTRY_AUTH_TOKEN": SENTRY_AUTH_TOKEN,
        "SENTRY_ORG": SENTRY_ORG,
        "GITHUB_TOKEN": GITHUB_TOKEN,
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Check your .env file"
        )

    print("✅ Environment validated")
    print(f"   Model: {MODEL_NAME}")
    print(f"   Sentry Org: {SENTRY_ORG}")
    print(f"   GitHub Repo: {GITHUB_OWNER}/{GITHUB_REPO}")


if __name__ == "__main__":
    # Test configuration
    validate_env()
    print(f"\n📋 Configuration:")
    print(f"   ANTHROPIC_API_KEY: {'✅ Set' if ANTHROPIC_API_KEY else '❌ Missing'}")
    print(f"   SENTRY_AUTH_TOKEN: {'✅ Set' if SENTRY_AUTH_TOKEN else '❌ Missing'}")
    print(f"   GITHUB_TOKEN: {'✅ Set' if GITHUB_TOKEN else '❌ Missing'}")
    print(f"   MEM0_API_KEY: {'✅ Set' if MEM0_API_KEY else '⚠️  Missing (optional)'}")
