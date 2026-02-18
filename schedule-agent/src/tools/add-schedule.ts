import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { DropboxService } from "../dropbox-service.js";
import { createGoogleCalendarEvent, findGoogleCalendarEvent, GCalResult } from "../gcal-client.js";
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
    "Add a new schedule to Notion and Google Calendar. Set create_folder=true only when the user explicitly says they will attend this event - this creates a Dropbox preparation folder.",
    {
      name: z.string().min(1),
      date_start: z.string().min(1),
      date_end: z.string().optional(),
      place: z.string().optional(),
      category: z.string().default("Spine"),
      society: z.array(z.string()).optional(),
      status: z.string().optional(),
      topic: z.string().optional(),
      link: z.string().url().optional(),
      abstract_deadline: z.string().optional(),
      create_folder: z.boolean().optional(),
    },
    async (params: AddScheduleParams) => {
      try {
        const notionDup = await notionClient.findDuplicate(params.name, params.date_start);
        let gcalDup: { exists: boolean; eventId?: string; eventUrl?: string } = { exists: false };
        try {
          gcalDup = await findGoogleCalendarEvent(params.name, params.date_start);
        } catch {
        }

        if (notionDup && gcalDup.exists) {
          return {
            content: [{ type: "text", text: JSON.stringify({
              success: false,
              message: "이미 등록된 일정입니다 (Notion + Google Calendar 모두 존재).",
              notion: { page_id: notionDup.page_id, url: notionDup.url, name: notionDup.name, date: notionDup.date_start },
              google_calendar: { eventId: gcalDup.eventId, eventUrl: gcalDup.eventUrl },
            }, null, 2) }],
          };
        }

        let notionResult: Record<string, unknown>;
        if (notionDup) {
          notionResult = { skipped: true, message: "이미 Notion에 등록되어 있습니다.", page_id: notionDup.page_id, url: notionDup.url };
        } else {
          const created = await notionClient.addSchedule(params);
          notionResult = { success: true, schedule: created };
        }

        let gcalResult: GCalResult;
        if (gcalDup.exists) {
          gcalResult = { success: false, message: "이미 Google Calendar에 등록되어 있습니다.", eventId: gcalDup.eventId, eventUrl: gcalDup.eventUrl };
        } else {
          try {
            gcalResult = await createGoogleCalendarEvent({
              name: params.name,
              dateStart: params.date_start,
              dateEnd: params.date_end,
              place: params.place,
              description: params.topic,
            });
          } catch (error) {
            gcalResult = {
              success: false,
              message: `Google Calendar error: ${error instanceof Error ? error.message : String(error)}`,
            };
          }
        }

        const response: Record<string, unknown> = {
          success: true,
          notion: notionResult,
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
