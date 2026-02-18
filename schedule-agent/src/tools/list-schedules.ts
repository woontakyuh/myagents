import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { ListSchedulesParams, NotionScheduleClient, ScheduleListItem } from "../notion-client.js";

function renderScheduleLine(item: ScheduleListItem): string {
  const dateText = item.date_end ? `${item.date_start} -> ${item.date_end}` : (item.date_start ?? "N/A");
  const placeText = item.place || "N/A";
  const statusText = item.status || "N/A";
  const categoryText = item.category || "N/A";
  return `- ${item.name} | Date: ${dateText} | Place: ${placeText} | Status: ${statusText} | Category: ${categoryText} | ID: ${item.page_id}`;
}

export function registerListSchedulesTool(server: McpServer, notionClient: NotionScheduleClient): void {
  server.tool(
    "list_schedules",
    {
      status: z.string().optional(),
      from_date: z.string().optional(),
      to_date: z.string().optional(),
      category: z.string().optional(),
      limit: z.number().int().positive().max(100).optional(),
    },
    async (params: ListSchedulesParams) => {
      try {
        const schedules = await notionClient.listSchedules(params);
        const text =
          schedules.length === 0
            ? "No schedules found."
            : [`Found ${schedules.length} schedule(s):`, ...schedules.map(renderScheduleLine)].join("\n");

        return {
          content: [{ type: "text", text }],
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: "text", text: `Failed to list schedules: ${message}` }],
          isError: true,
        };
      }
    },
  );
}
