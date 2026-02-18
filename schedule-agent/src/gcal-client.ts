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

function nextDay(dateStr: string): string {
  const d = new Date(`${dateStr}T00:00:00`);
  d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}
