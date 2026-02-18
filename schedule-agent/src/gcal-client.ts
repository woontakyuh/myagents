import { google, calendar_v3 } from "googleapis";
import { getAuthorizedClient } from "./gcal-auth.js";

export interface GCalResult {
  success: boolean;
  message: string;
  eventId?: string;
  eventUrl?: string;
}

export interface GCalEventInput {
  name: string;
  dateStart: string;
  dateEnd?: string;
  place?: string;
  description?: string;
}

export async function createGoogleCalendarEvent(input: GCalEventInput): Promise<GCalResult> {
  const auth = await getAuthorizedClient();
  if (!auth) {
    return {
      success: false,
      message: "Google Calendar not configured. Run: node build/auth-setup.js",
    };
  }

  const calendar = google.calendar({ version: "v3", auth });

  const event: calendar_v3.Schema$Event = {
    summary: input.name,
    location: input.place,
    description: input.description,
    start: {
      date: input.dateStart,
      timeZone: "Asia/Seoul",
    },
    end: {
      date: input.dateEnd ? nextDay(input.dateEnd) : nextDay(input.dateStart),
      timeZone: "Asia/Seoul",
    },
  };

  const res = await calendar.events.insert({
    calendarId: "primary",
    requestBody: event,
  });

  return {
    success: true,
    message: "Event created in Google Calendar",
    eventId: res.data.id ?? undefined,
    eventUrl: res.data.htmlLink ?? undefined,
  };
}

export async function findGoogleCalendarEvent(name: string, dateStart: string): Promise<{ exists: boolean; eventId?: string; eventUrl?: string }> {
  const auth = await getAuthorizedClient();
  if (!auth) {
    return { exists: false };
  }

  const calendar = google.calendar({ version: "v3", auth });
  const res = await calendar.events.list({
    calendarId: "primary",
    timeMin: `${dateStart}T00:00:00+09:00`,
    timeMax: `${nextDay(dateStart)}T00:00:00+09:00`,
    q: name,
    singleEvents: true,
    maxResults: 5,
  });

  const match = (res.data.items ?? []).find(
    (e) => e.summary?.toLowerCase() === name.toLowerCase(),
  );

  if (match) {
    return { exists: true, eventId: match.id ?? undefined, eventUrl: match.htmlLink ?? undefined };
  }
  return { exists: false };
}

function nextDay(dateStr: string): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  const d = new Date(year, month - 1, day + 1);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}
