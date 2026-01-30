#!/usr/bin/env node
/**
 * PostHog MCP Server
 * Provides PostHog analytics and session replay tools via MCP
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const POSTHOG_HOST = process.env.POSTHOG_HOST || "https://us.posthog.com";
const POSTHOG_API_KEY = process.env.POSTHOG_API_KEY;
const POSTHOG_PROJECT_ID = process.env.POSTHOG_PROJECT_ID;

if (!POSTHOG_API_KEY || !POSTHOG_PROJECT_ID) {
  console.error("Error: POSTHOG_API_KEY and POSTHOG_PROJECT_ID are required");
  process.exit(1);
}

class PostHogServer {
  constructor() {
    this.server = new Server(
      {
        name: "posthog-mcp-server",
        version: "1.0.0",
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupHandlers();
    this.server.onerror = (error) => console.error("[MCP Error]", error);
    process.on("SIGINT", async () => {
      await this.server.close();
      process.exit(0);
    });
  }

  setupHandlers() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: [
        {
          name: "get_session_recordings",
          description: "Get session recordings matching filters",
          inputSchema: {
            type: "object",
            properties: {
              limit: {
                type: "number",
                description: "Number of recordings to return (default: 10)",
              },
              person_uuid: {
                type: "string",
                description: "Filter by person UUID",
              },
              events: {
                type: "array",
                description: "Filter by events",
                items: { type: "object" },
              },
            },
          },
        },
        {
          name: "get_events",
          description: "Get events matching filters",
          inputSchema: {
            type: "object",
            properties: {
              event: {
                type: "string",
                description: "Event name to filter by",
              },
              properties: {
                type: "array",
                description: "Property filters",
                items: { type: "object" },
              },
              limit: {
                type: "number",
                description: "Number of events to return (default: 100)",
              },
            },
          },
        },
        {
          name: "get_person",
          description: "Get person details by distinct_id",
          inputSchema: {
            type: "object",
            properties: {
              distinct_id: {
                type: "string",
                description: "Person distinct ID",
              },
            },
            required: ["distinct_id"],
          },
        },
      ],
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        switch (name) {
          case "get_session_recordings":
            return await this.getSessionRecordings(args);
          case "get_events":
            return await this.getEvents(args);
          case "get_person":
            return await this.getPerson(args);
          default:
            throw new Error(`Unknown tool: ${name}`);
        }
      } catch (error) {
        return {
          content: [
            {
              type: "text",
              text: `Error: ${error.message}`,
            },
          ],
        };
      }
    });
  }

  async getSessionRecordings(args) {
    const url = `${POSTHOG_HOST}/api/projects/${POSTHOG_PROJECT_ID}/session_recordings`;
    const params = new URLSearchParams({
      limit: args.limit || 10,
    });

    const response = await fetch(`${url}?${params}`, {
      headers: {
        Authorization: `Bearer ${POSTHOG_API_KEY}`,
      },
    });

    if (!response.ok) {
      throw new Error(`PostHog API error: ${response.statusText}`);
    }

    const data = await response.json();
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  async getEvents(args) {
    const url = `${POSTHOG_HOST}/api/projects/${POSTHOG_PROJECT_ID}/events`;
    const params = new URLSearchParams({
      limit: args.limit || 100,
    });

    if (args.event) {
      params.append("event", args.event);
    }

    const response = await fetch(`${url}?${params}`, {
      headers: {
        Authorization: `Bearer ${POSTHOG_API_KEY}`,
      },
    });

    if (!response.ok) {
      throw new Error(`PostHog API error: ${response.statusText}`);
    }

    const data = await response.json();
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  async getPerson(args) {
    const url = `${POSTHOG_HOST}/api/projects/${POSTHOG_PROJECT_ID}/persons`;
    const params = new URLSearchParams({
      distinct_id: args.distinct_id,
    });

    const response = await fetch(`${url}?${params}`, {
      headers: {
        Authorization: `Bearer ${POSTHOG_API_KEY}`,
      },
    });

    if (!response.ok) {
      throw new Error(`PostHog API error: ${response.statusText}`);
    }

    const data = await response.json();
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(data, null, 2),
        },
      ],
    };
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error("PostHog MCP server running on stdio");
  }
}

const server = new PostHogServer();
server.run().catch(console.error);
