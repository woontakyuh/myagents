#!/usr/bin/env node

import * as http from "node:http";
import { google } from "googleapis";
import { loadCredentials, saveTokens } from "./gcal-auth.js";

const SCOPES = ["https://www.googleapis.com/auth/calendar.events"];
const REDIRECT_PORT = 3000;

async function main(): Promise<void> {
  const creds = loadCredentials();
  if (!creds) {
    console.error("credentials.json not found at ~/.config/schedule-agent/credentials.json");
    console.error("Download it from Google Cloud Console -> APIs & Services -> Credentials");
    process.exit(1);
  }

  const oauth2Client = new google.auth.OAuth2(
    creds.client_id,
    creds.client_secret,
    `http://localhost:${REDIRECT_PORT}`,
  );

  const authUrl = oauth2Client.generateAuthUrl({
    access_type: "offline",
    scope: SCOPES,
    prompt: "consent",
  });

  console.log("\nOpen this URL in your browser:\n");
  console.log(authUrl);
  console.log("\nWaiting for authorization...\n");

  const server = http.createServer(async (req, res) => {
    const requestUrl = req.url ?? "/";
    const url = new URL(requestUrl, `http://localhost:${REDIRECT_PORT}`);
    const code = url.searchParams.get("code");

    if (!code) {
      res.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("No authorization code received");
      return;
    }

    try {
      const { tokens } = await oauth2Client.getToken(code);
      saveTokens(tokens);

      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end("<h1>Authorization successful. You can close this tab.</h1>");

      console.log("Token saved successfully.");
      console.log("You can now use Google Calendar with the schedule agent.");

      server.close(() => {
        process.exit(0);
      });
    } catch (error) {
      res.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
      res.end("Failed to exchange code for tokens");

      const message = error instanceof Error ? error.message : String(error);
      console.error(`Error: ${message}`);

      server.close(() => {
        process.exit(1);
      });
    }
  });

  server.listen(REDIRECT_PORT, () => {
    console.log(`Listening on http://localhost:${REDIRECT_PORT} for OAuth callback...`);
  });
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`auth-setup failed: ${message}`);
  process.exit(1);
});
