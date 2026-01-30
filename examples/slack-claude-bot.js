#!/usr/bin/env node
/**
 * Slack Bot that uses Claude Code CLI for Sentry incident response
 *
 * Usage:
 *   /fix-sentry 7088840785
 *   /analyze-recent-errors
 *
 * Based on: https://github.com/MattKilmer/claude-autofix-bot
 */

const { App } = require('@slack/bolt');
const { exec } = require('child_process');
const { promisify } = require('util');
const fs = require('fs').promises;

const execAsync = promisify(exec);

// Initialize Slack app
const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  signingSecret: process.env.SLACK_SIGNING_SECRET,
  socketMode: true,
  appToken: process.env.SLACK_APP_TOKEN
});

// Store active sessions
const activeSessions = new Map();

/**
 * Slash command: /fix-sentry <issue_id>
 * Triggers Claude Code to analyze and fix a Sentry issue
 */
app.command('/fix-sentry', async ({ command, ack, respond, client }) => {
  await ack();

  const issueId = command.text.trim();

  if (!issueId) {
    await respond({
      text: '❌ Please provide a Sentry issue ID: `/fix-sentry 7088840785`',
      response_type: 'ephemeral'
    });
    return;
  }

  // Send initial response
  await respond({
    text: `🔄 Starting analysis of Sentry issue \`${issueId}\`...`,
    response_type: 'in_channel'
  });

  try {
    // Create Claude Code prompt
    const prompt = `
# Sentry Issue Auto-Fix Task

## Issue ID: ${issueId}

## Instructions:
1. Use mcp__sentry__get_issue_details to fetch the full issue
2. Analyze the stack trace and error message
3. Use mcp__github__get_file_contents to read the buggy code
4. Determine root cause
5. Generate a minimal fix
6. Create unit tests
7. Use mcp__github__create_pull_request to submit the fix

## Return Format:
Return ONLY a JSON object:
{
  "root_cause": "...",
  "confidence": 0.85,
  "pr_url": "https://github.com/...",
  "pr_number": 123,
  "files_changed": ["file1.py", "file2.py"],
  "tests_added": true
}
`;

    // Execute Claude Code with Opus model
    console.log(`[${new Date().toISOString()}] Executing Claude Code for issue ${issueId}`);

    const { stdout, stderr } = await execAsync(
      `claude -p ${JSON.stringify(prompt)} --model opus --output json`,
      {
        timeout: 300000, // 5 minute timeout
        maxBuffer: 10 * 1024 * 1024 // 10MB buffer
      }
    );

    if (stderr) {
      console.error('Claude Code stderr:', stderr);
    }

    // Parse result
    let result;
    try {
      // Extract JSON from stdout (Claude might add extra text)
      const jsonMatch = stdout.match(/\{[\s\S]*\}/);
      result = JSON.parse(jsonMatch ? jsonMatch[0] : stdout);
    } catch (e) {
      throw new Error(`Failed to parse Claude output: ${e.message}\n${stdout}`);
    }

    // Send success message to Slack
    const confidence = (result.confidence * 100).toFixed(0);
    const emoji = result.confidence >= 0.8 ? '✅' : '⚠️';

    await client.chat.postMessage({
      channel: command.channel_id,
      text: `${emoji} Analysis Complete for Issue \`${issueId}\``,
      blocks: [
        {
          type: 'header',
          text: {
            type: 'plain_text',
            text: `${emoji} Sentry Issue Auto-Fixed`,
            emoji: true
          }
        },
        {
          type: 'section',
          fields: [
            {
              type: 'mrkdwn',
              text: `*Issue ID:*\n<https://sentry.io/organizations/${process.env.SENTRY_ORG}/issues/${issueId}/|${issueId}>`
            },
            {
              type: 'mrkdwn',
              text: `*Confidence:*\n${confidence}%`
            }
          ]
        },
        {
          type: 'section',
          text: {
            type: 'mrkdwn',
            text: `*Root Cause:*\n${result.root_cause}`
          }
        },
        {
          type: 'section',
          fields: [
            {
              type: 'mrkdwn',
              text: `*Files Changed:*\n${result.files_changed.join(', ')}`
            },
            {
              type: 'mrkdwn',
              text: `*Tests Added:*\n${result.tests_added ? 'Yes ✅' : 'No ❌'}`
            }
          ]
        },
        {
          type: 'actions',
          elements: [
            {
              type: 'button',
              text: {
                type: 'plain_text',
                text: 'View PR',
                emoji: true
              },
              url: result.pr_url,
              style: 'primary'
            },
            {
              type: 'button',
              text: {
                type: 'plain_text',
                text: 'View Issue',
                emoji: true
              },
              url: `https://sentry.io/organizations/${process.env.SENTRY_ORG}/issues/${issueId}/`
            }
          ]
        }
      ]
    });

    // Store result for follow-up
    activeSessions.set(issueId, result);

  } catch (error) {
    console.error('Error processing Sentry issue:', error);

    await client.chat.postMessage({
      channel: command.channel_id,
      text: `❌ Failed to analyze issue \`${issueId}\`: ${error.message}`,
      response_type: 'ephemeral'
    });
  }
});

/**
 * Slash command: /analyze-recent-errors
 * Scans Sentry for recent errors and prioritizes them
 */
app.command('/analyze-recent-errors', async ({ command, ack, respond, client }) => {
  await ack();

  await respond({
    text: '🔍 Scanning Sentry for recent errors...',
    response_type: 'in_channel'
  });

  try {
    const prompt = `
# Sentry Error Discovery Task

## Instructions:
1. Use mcp__sentry__search_issues with query "is:unresolved" and sort by "freq"
2. Fetch the top 10 most frequent issues
3. For each issue, calculate a priority score based on:
   - Error frequency (count)
   - User impact (userCount)
   - Recent activity (lastSeen)
4. Return a ranked list

## Return Format:
{
  "total_issues": 10,
  "high_priority": [
    {
      "issue_id": "...",
      "title": "...",
      "priority": 95,
      "count": 1000,
      "user_count": 50,
      "recommendation": "Auto-fix recommended"
    }
  ],
  "medium_priority": [...],
  "low_priority": [...]
}
`;

    const { stdout } = await execAsync(
      `claude -p ${JSON.stringify(prompt)} --model opus --output json`,
      { timeout: 120000 }
    );

    const jsonMatch = stdout.match(/\{[\s\S]*\}/);
    const result = JSON.parse(jsonMatch ? jsonMatch[0] : stdout);

    // Build Slack message
    const blocks = [
      {
        type: 'header',
        text: {
          type: 'plain_text',
          text: '📊 Sentry Error Analysis',
          emoji: true
        }
      },
      {
        type: 'section',
        text: {
          type: 'mrkdwn',
          text: `Found *${result.total_issues}* unresolved issues. Here are the top priorities:`
        }
      }
    ];

    // Add high priority issues
    if (result.high_priority && result.high_priority.length > 0) {
      blocks.push({
        type: 'section',
        text: {
          type: 'mrkdwn',
          text: '*🔴 High Priority Issues*'
        }
      });

      result.high_priority.forEach(issue => {
        blocks.push(
          {
            type: 'section',
            text: {
              type: 'mrkdwn',
              text: `*${issue.title}*\nPriority: ${issue.priority} | Count: ${issue.count} | Users: ${issue.user_count}\n_${issue.recommendation}_`
            },
            accessory: {
              type: 'button',
              text: {
                type: 'plain_text',
                text: 'Auto-Fix',
                emoji: true
              },
              value: issue.issue_id,
              action_id: `fix_issue_${issue.issue_id}`,
              style: 'danger'
            }
          },
          { type: 'divider' }
        );
      });
    }

    await client.chat.postMessage({
      channel: command.channel_id,
      blocks
    });

  } catch (error) {
    console.error('Error analyzing recent errors:', error);

    await client.chat.postMessage({
      channel: command.channel_id,
      text: `❌ Failed to analyze recent errors: ${error.message}`,
      response_type: 'ephemeral'
    });
  }
});

/**
 * Button action: Auto-fix issue
 */
app.action(/^fix_issue_(.+)$/, async ({ action, ack, respond, client, body }) => {
  await ack();

  const issueId = action.action_id.replace('fix_issue_', '');

  // Update message to show it's processing
  await client.chat.update({
    channel: body.channel.id,
    ts: body.message.ts,
    text: `🔄 Starting auto-fix for issue \`${issueId}\`...`
  });

  // Trigger the fix (reuse logic from /fix-sentry)
  // ... (implementation similar to above)
});

/**
 * Cron job: Run every hour to check for new high-priority issues
 */
async function scheduledScan() {
  console.log('[CRON] Running scheduled Sentry scan...');

  try {
    const prompt = `
Check Sentry for new high-priority issues (priority >= 80) in the last hour.
If found, return a summary. Otherwise, return {"new_issues": 0}.
`;

    const { stdout } = await execAsync(
      `claude -p ${JSON.stringify(prompt)} --model sonnet --output json`,
      { timeout: 60000 }
    );

    const result = JSON.parse(stdout.match(/\{[\s\S]*\}/)[0]);

    if (result.new_issues > 0) {
      // Post to #incidents channel
      await app.client.chat.postMessage({
        channel: process.env.SLACK_INCIDENTS_CHANNEL,
        text: `🚨 ${result.new_issues} new high-priority Sentry issues detected!`,
        blocks: [
          {
            type: 'section',
            text: {
              type: 'mrkdwn',
              text: `*🚨 New High-Priority Issues*\n${result.summary}`
            }
          },
          {
            type: 'actions',
            elements: [
              {
                type: 'button',
                text: {
                  type: 'plain_text',
                  text: 'Analyze All',
                  emoji: true
                },
                value: 'analyze_all',
                action_id: 'analyze_all_issues',
                style: 'danger'
              }
            ]
          }
        ]
      });
    }
  } catch (error) {
    console.error('[CRON] Scheduled scan failed:', error);
  }
}

// Run cron every hour
setInterval(scheduledScan, 60 * 60 * 1000);

// Start the app
(async () => {
  await app.start();
  console.log('⚡️ Slack bot is running!');
  console.log('Available commands:');
  console.log('  /fix-sentry <issue_id>');
  console.log('  /analyze-recent-errors');
})();
