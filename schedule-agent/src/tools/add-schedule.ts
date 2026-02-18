import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { DropboxService } from "../dropbox-service.js";
import { createGoogleCalendarEvent } from "../gcal-client.js";
import { NotionScheduleClient, ScheduleMutationInput } from "../notion-client.js";

interface AddScheduleParams extends ScheduleMutationInput {
  name: string;
  date_start: string;
  create_folder?: boolean;
}

export function registerAddScheduleTool(
  server: McpServer,
  notionClient: NotionScheduleClient,
  dropboxService: DropboxService,
): void {
  server.tool(
    "add_schedule",
    {
      name: z.string().min(1),
      date_start: z.string().min(1),
      date_end: z.string().optional(),
      place: z.string().optional(),
      category: z.string().optional(),
      society: z.array(z.string()).optional(),
      status: z.string().optional(),
      topic: z.string().optional(),
      link: z.string().url().optional(),
      abstract_deadline: z.string().optional(),
      create_folder: z.boolean().optional(),
    },
    async (params: AddScheduleParams) => {
      try {
        const created = await notionClient.addSchedule(params);

        const gcalResult = await createGoogleCalendarEvent({
          name: params.name,
          dateStart: params.date_start,
          dateEnd: params.date_end,
          place: params.place,
        });

        const response: Record<string, unknown> = {
          success: true,
          schedule: created,
          google_calendar: gcalResult,
        };

        if (params.create_folder) {
          const folder = dropboxService.createEventFolder(params.name, params.date_start);
          response.folder = folder;
        }

        return {
          content: [{ type: "text", text: JSON.stringify(response, null, 2) }],
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: "text", text: `Failed to add schedule: ${message}` }],
          isError: true,
        };
      }
    },
  );
}
