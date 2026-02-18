import { readFileSync } from "node:fs";
import { join } from "node:path";

const DEFAULT_ENV_PATH = join(process.env.HOME ?? "", ".journal_alert_env");
const NOTION_DATABASE_ID = "2fde4781-d308-4061-ac67-fcbc7f67fc2a";
const NOTION_API_VERSION = "2022-06-28";

export interface AppConfig {
  notionToken: string;
  notionDatabaseId: string;
  notionApiVersion: string;
  envFilePath: string;
}

function stripQuotes(value: string): string {
  if (
    (value.startsWith("\"") && value.endsWith("\"")) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

export function loadEnvFile(filePath: string = DEFAULT_ENV_PATH): Record<string, string> {
  const parsed: Record<string, string> = {};

  try {
    const content = readFileSync(filePath, "utf-8");
    for (const rawLine of content.split(/\r?\n/u)) {
      const line = rawLine.trim();
      if (line.length === 0 || line.startsWith("#")) {
        continue;
      }

      const match = /^export\s+([A-Z0-9_]+)=(.*)$/u.exec(line);
      if (!match) {
        continue;
      }

      const key = match[1];
      const value = stripQuotes(match[2].trim());
      parsed[key] = value;

      if (!process.env[key]) {
        process.env[key] = value;
      }
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`Failed to read env file at ${filePath}: ${message}`);
  }

  return parsed;
}

export function getConfig(): AppConfig {
  loadEnvFile(DEFAULT_ENV_PATH);

  const notionToken = process.env.NOTION_TOKEN?.trim();
  if (!notionToken) {
    throw new Error(`NOTION_TOKEN is missing in ${DEFAULT_ENV_PATH}`);
  }

  return {
    notionToken,
    notionDatabaseId: NOTION_DATABASE_ID,
    notionApiVersion: NOTION_API_VERSION,
    envFilePath: DEFAULT_ENV_PATH,
  };
}
