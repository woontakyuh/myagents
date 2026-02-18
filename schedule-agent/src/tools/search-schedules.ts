import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { NotionScheduleClient, ScheduleListItem } from "../notion-client.js";

interface SearchSchedulesParams {
  query: string;
  limit?: number;
}

function renderScheduleLine(item: ScheduleListItem): string {
  const dateText = item.date_end ? `${item.date_start} -> ${item.date_end}` : (item.date_start ?? "N/A");
  return `- ${item.name} | Date: ${dateText} | Place: ${item.place || "N/A"} | Status: ${item.status || "N/A"} | Category: ${item.category || "N/A"} | ID: ${item.page_id}`;
}

export function registerSearchSchedulesTool(server: McpServer, notionClient: NotionScheduleClient): void {
  server.tool(
    "search_schedules",
    {
      query: z.string().min(1),
      limit: z.number().int().positive().max(100).optional(),
    },
    async (params: SearchSchedulesParams) => {
      try {
        const schedules = await notionClient.searchSchedules(params.query, params.limit ?? 20);
        const text =
          schedules.length === 0
            ? `No schedules found for query: ${params.query}`
            : [`Found ${schedules.length} matching schedule(s):`, ...schedules.map(renderScheduleLine)].join("\n");

        return {
          content: [{ type: "text", text }],
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: "text", text: `Failed to search schedules: ${message}` }],
          isError: true,
        };
      }
    },
  );
}
