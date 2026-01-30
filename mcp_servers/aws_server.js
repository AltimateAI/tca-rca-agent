#!/usr/bin/env node
/**
 * AWS MCP Server
 * Provides AWS CloudWatch, X-Ray, and ECS tools via MCP
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import {
  CloudWatchLogsClient,
  FilterLogEventsCommand,
} from "@aws-sdk/client-cloudwatch-logs";
import { XRayClient, GetTraceSummariesCommand } from "@aws-sdk/client-xray";
import { ECSClient, DescribeTasksCommand } from "@aws-sdk/client-ecs";

const AWS_REGION = process.env.AWS_REGION || "us-east-1";

class AWSServer {
  constructor() {
    this.cloudwatchLogs = new CloudWatchLogsClient({ region: AWS_REGION });
    this.xray = new XRayClient({ region: AWS_REGION });
    this.ecs = new ECSClient({ region: AWS_REGION });

    this.server = new Server(
      {
        name: "aws-mcp-server",
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
          name: "get_cloudwatch_logs",
          description: "Get CloudWatch logs matching filter pattern",
          inputSchema: {
            type: "object",
            properties: {
              log_group: {
                type: "string",
                description: "CloudWatch log group name",
              },
              filter_pattern: {
                type: "string",
                description: "Filter pattern for logs",
              },
              start_time: {
                type: "string",
                description: "Start time (ISO 8601)",
              },
              limit: {
                type: "number",
                description: "Max number of log events (default: 100)",
              },
            },
            required: ["log_group"],
          },
        },
        {
          name: "get_xray_traces",
          description: "Get X-Ray traces for time range",
          inputSchema: {
            type: "object",
            properties: {
              start_time: {
                type: "string",
                description: "Start time (ISO 8601)",
              },
              filter_expression: {
                type: "string",
                description: "X-Ray filter expression",
              },
            },
            required: ["start_time"],
          },
        },
        {
          name: "get_ecs_task_logs",
          description: "Get logs for specific ECS task",
          inputSchema: {
            type: "object",
            properties: {
              cluster: {
                type: "string",
                description: "ECS cluster name",
              },
              task_arn: {
                type: "string",
                description: "ECS task ARN",
              },
            },
            required: ["cluster", "task_arn"],
          },
        },
      ],
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        switch (name) {
          case "get_cloudwatch_logs":
            return await this.getCloudWatchLogs(args);
          case "get_xray_traces":
            return await this.getXRayTraces(args);
          case "get_ecs_task_logs":
            return await this.getECSTaskLogs(args);
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

  async getCloudWatchLogs(args) {
    const startTime = args.start_time
      ? new Date(args.start_time).getTime()
      : Date.now() - 3600000; // Default: 1 hour ago

    const command = new FilterLogEventsCommand({
      logGroupName: args.log_group,
      filterPattern: args.filter_pattern || "",
      startTime: startTime,
      limit: args.limit || 100,
    });

    const response = await this.cloudwatchLogs.send(command);
    const logs = response.events || [];

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(
            {
              log_group: args.log_group,
              count: logs.length,
              logs: logs.map((e) => ({
                timestamp: new Date(e.timestamp).toISOString(),
                message: e.message,
              })),
            },
            null,
            2
          ),
        },
      ],
    };
  }

  async getXRayTraces(args) {
    const startTime = new Date(args.start_time);
    const endTime = new Date();

    const command = new GetTraceSummariesCommand({
      StartTime: startTime,
      EndTime: endTime,
      FilterExpression: args.filter_expression,
    });

    const response = await this.xray.send(command);
    const traces = response.TraceSummaries || [];

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(
            {
              count: traces.length,
              traces: traces.slice(0, 10).map((t) => ({
                id: t.Id,
                duration: t.Duration,
                response_time: t.ResponseTime,
                has_error: t.HasError,
                has_fault: t.HasFault,
              })),
            },
            null,
            2
          ),
        },
      ],
    };
  }

  async getECSTaskLogs(args) {
    const command = new DescribeTasksCommand({
      cluster: args.cluster,
      tasks: [args.task_arn],
    });

    const response = await this.ecs.send(command);
    const task = response.tasks?.[0];

    if (!task) {
      throw new Error("Task not found");
    }

    const container = task.containers?.[0];
    const logConfig = container?.logConfiguration;

    if (!logConfig || logConfig.logDriver !== "awslogs") {
      throw new Error("Task does not use CloudWatch logs");
    }

    const logGroup = logConfig.options["awslogs-group"];
    const logStream = container.logStreamName;

    // Get logs from CloudWatch
    const logsCommand = new FilterLogEventsCommand({
      logGroupName: logGroup,
      logStreamNames: [logStream],
      limit: 100,
    });

    const logsResponse = await this.cloudwatchLogs.send(logsCommand);
    const logs = logsResponse.events || [];

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(
            {
              task_arn: args.task_arn,
              log_group: logGroup,
              log_stream: logStream,
              count: logs.length,
              logs: logs.map((e) => ({
                timestamp: new Date(e.timestamp).toISOString(),
                message: e.message,
              })),
            },
            null,
            2
          ),
        },
      ],
    };
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error("AWS MCP server running on stdio");
  }
}

const server = new AWSServer();
server.run().catch(console.error);
