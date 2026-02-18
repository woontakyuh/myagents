import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { NotionScheduleClient } from "../notion-client.js";

interface GetScheduleParams {
  page_id: string;
}

export function registerGetScheduleTool(server: McpServer, notionClient: NotionScheduleClient): void {
  server.tool(
    "get_schedule",
    {
      page_id: z.string().min(1),
    },
    async (params: GetScheduleParams) => {
      try {
        const schedule = await notionClient.getSchedule(params.page_id);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(schedule, null, 2),
            },
          ],
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: "text", text: `Failed to get schedule: ${message}` }],
          isError: true,
        };
      }
    },
  );
}
