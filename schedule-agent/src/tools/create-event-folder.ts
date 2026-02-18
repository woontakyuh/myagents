import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { DropboxService } from "../dropbox-service.js";

interface CreateEventFolderParams {
  name: string;
  date: string;
}

export function registerCreateEventFolderTool(server: McpServer, dropboxService: DropboxService): void {
  server.tool(
    "create_event_folder",
    {
      name: z.string().min(1),
      date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/u, "date must be yyyy-mm-dd"),
    },
    async (params: CreateEventFolderParams) => {
      try {
        const result = dropboxService.createEventFolder(params.name, params.date);
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(
                {
                  success: true,
                  path: result.path,
                  existed: result.existed,
                },
                null,
                2,
              ),
            },
          ],
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          content: [{ type: "text", text: `Failed to create event folder: ${message}` }],
          isError: true,
        };
      }
    },
  );
}
