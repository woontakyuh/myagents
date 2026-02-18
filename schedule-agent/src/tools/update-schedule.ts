import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { NotionScheduleClient, ScheduleMutationInput } from "../notion-client.js";

interface UpdateScheduleParams extends ScheduleMutationInput {
  page_id: string;
}

export function registerUpdateScheduleTool(server: McpServer, notionClient: NotionScheduleClient): void {
  server.tool(
    "update_schedule",
    {
      page_id: z.string().min(1),
      name: z.string().optional(),
      date_start: z.string().optional(),
      date_end: z.string().optional(),
      place: z.string().optional(),
      category: z.string().optional(),
      society: z.array(z.string()).optional(),
      status: z.string().optional(),
      topic: z.string().optional(),
      link: z.string().url().optional(),
      abstract_deadline: z.string().optional(),
    },
    async (params: UpdateScheduleParams) => {
      try {
        const { page_id, ...updates } = params;
        const updated = await notionClient.updateSchedule(page_id, updates);

        return {
          content: [{ type: "text", text: JSON.stringify({ success: true, schedule: updated }, null, 2) }],
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: "text", text: `Failed to update schedule: ${message}` }],
          isError: true,
        };
      }
    },
  );
}
