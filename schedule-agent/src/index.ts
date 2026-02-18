#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { getConfig } from "./config.js";
import { DropboxService } from "./dropbox-service.js";
import { NotionScheduleClient } from "./notion-client.js";
import { registerAddScheduleTool } from "./tools/add-schedule.js";
import { registerCreateEventFolderTool } from "./tools/create-event-folder.js";
import { registerGetScheduleTool } from "./tools/get-schedule.js";
import { registerListSchedulesTool } from "./tools/list-schedules.js";
import { registerSearchSchedulesTool } from "./tools/search-schedules.js";
import { registerUpdateScheduleTool } from "./tools/update-schedule.js";

async function main(): Promise<void> {
  const config = getConfig();

  const server = new McpServer({
    name: "schedule-agent",
    version: "1.0.0",
  });

  const notionClient = new NotionScheduleClient(config);
  const dropboxService = new DropboxService();

  registerListSchedulesTool(server, notionClient);
  registerSearchSchedulesTool(server, notionClient);
  registerGetScheduleTool(server, notionClient);
  registerAddScheduleTool(server, notionClient, dropboxService);
  registerUpdateScheduleTool(server, notionClient);
  registerCreateEventFolderTool(server, dropboxService);

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`schedule-agent failed to start: ${message}\n`);
  process.exit(1);
});
