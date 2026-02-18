import { chmodSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { google } from "googleapis";
import type { Credentials } from "google-auth-library";

const SCOPES = ["https://www.googleapis.com/auth/calendar.events"];
const CONFIG_DIR = path.join(os.homedir(), ".config", "schedule-agent");
const CREDENTIALS_PATH = path.join(CONFIG_DIR, "credentials.json");
const TOKEN_PATH = path.join(CONFIG_DIR, "token.json");

interface OAuthInstalledCredentials {
  client_id: string;
  client_secret: string;
  redirect_uris: string[];
}

interface CredentialsFile {
  installed?: OAuthInstalledCredentials;
}

export function loadCredentials(): OAuthInstalledCredentials | null {
  if (!existsSync(CREDENTIALS_PATH)) {
    return null;
  }

  const raw = readFileSync(CREDENTIALS_PATH, "utf-8");
  const parsed = JSON.parse(raw) as CredentialsFile;

  if (!parsed.installed) {
    throw new Error("Invalid credentials.json: missing installed key");
  }

  return parsed.installed;
}

export function loadStoredTokens(): Credentials | null {
  if (!existsSync(TOKEN_PATH)) {
    return null;
  }

  const raw = readFileSync(TOKEN_PATH, "utf-8");
  return JSON.parse(raw) as Credentials;
}

export function saveTokens(tokens: Credentials): void {
  mkdirSync(CONFIG_DIR, { recursive: true });
  writeFileSync(TOKEN_PATH, JSON.stringify(tokens, null, 2), "utf-8");
  chmodSync(TOKEN_PATH, 0o600);
}

export async function getAuthorizedClient(): Promise<InstanceType<typeof google.auth.OAuth2> | null> {
  const credentials = loadCredentials();
  if (!credentials) {
    return null;
  }

  const storedTokens = loadStoredTokens();
  if (!storedTokens) {
    return null;
  }

  const oauth2Client = new google.auth.OAuth2(
    credentials.client_id,
    credentials.client_secret,
    credentials.redirect_uris[0] ?? "http://localhost:3000",
  );

  oauth2Client.setCredentials(storedTokens);
  oauth2Client.on("tokens", (tokens: Credentials) => {
    saveTokens({ ...oauth2Client.credentials, ...tokens, scope: SCOPES.join(" ") });
  });

  return oauth2Client;
}
