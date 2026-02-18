import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { GCalResult, updateGoogleCalendarEvent } from "../gcal-client.js";
import { NotionScheduleClient, ScheduleMutationInput } from "../notion-client.js";

interface UpdateScheduleParams extends ScheduleMutationInput {
  page_id: string;
}

export function registerUpdateScheduleTool(server: McpServer, notionClient: NotionScheduleClient): void {
  server.tool(
    "update_schedule",
    "Update an existing schedule in both Notion and Google Calendar. Finds the GCal event by current name and date, then applies changes to both.",
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

        const current = await notionClient.getSchedule(page_id);
        const oldName = (current.properties.Name as string) || "";
        const dateProps = current.properties.Date as { start: string; end: string | null } | null;
        const oldDateStart = dateProps?.start ?? "";

        const notionResult = await notionClient.updateSchedule(page_id, updates);

        let gcalResult: GCalResult;
        if (oldName && oldDateStart) {
          try {
            gcalResult = await updateGoogleCalendarEvent(oldName, oldDateStart, {
              name: updates.name,
              dateStart: updates.date_start,
              dateEnd: updates.date_end,
              place: updates.place,
              description: updates.topic,
            });
          } catch (error) {
            gcalResult = {
              success: false,
              message: `Google Calendar error: ${error instanceof Error ? error.message : String(error)}`,
            };
          }
        } else {
          gcalResult = { success: false, message: "기존 일정의 이름/날짜를 확인할 수 없어 GCal 업데이트를 건너뜁니다." };
        }

        return {
          content: [{ type: "text", text: JSON.stringify({
            success: true,
            notion: { success: true, schedule: notionResult },
            google_calendar: gcalResult,
          }, null, 2) }],
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
