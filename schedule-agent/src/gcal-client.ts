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

const TIMEZONE = "Asia/Seoul";

function hasTimeComponent(dateStr: string): boolean {
  return dateStr.includes("T");
}

function extractDate(dateStr: string): string {
  return dateStr.slice(0, 10);
}

// Append +09:00 (KST) if no timezone offset present — prevents UTC misinterpretation
function ensureTimezone(dateTimeStr: string): string {
  if (/[+-]\d{2}:\d{2}$/u.test(dateTimeStr) || dateTimeStr.endsWith("Z")) {
    return dateTimeStr;
  }
  return `${dateTimeStr}+09:00`;
}

function buildEventTiming(
  dateStart: string,
  dateEnd?: string,
): { start: calendar_v3.Schema$EventDateTime; end: calendar_v3.Schema$EventDateTime } {
  const isTimed = hasTimeComponent(dateStart);

  if (isTimed) {
    const endStr = dateEnd && hasTimeComponent(dateEnd)
      ? ensureTimezone(dateEnd)
      : ensureTimezone(dateStart);
    return {
      start: { dateTime: ensureTimezone(dateStart), timeZone: TIMEZONE },
      end: { dateTime: endStr, timeZone: TIMEZONE },
    };
  }

  return {
    start: { date: extractDate(dateStart), timeZone: TIMEZONE },
    end: { date: dateEnd ? nextDay(extractDate(dateEnd)) : nextDay(extractDate(dateStart)), timeZone: TIMEZONE },
  };
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
  const timing = buildEventTiming(input.dateStart, input.dateEnd);

  const event: calendar_v3.Schema$Event = {
    summary: input.name,
    location: input.place,
    description: input.description,
    start: timing.start,
    end: timing.end,
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

  const dateOnly = extractDate(dateStart);
  const calendar = google.calendar({ version: "v3", auth });
  const res = await calendar.events.list({
    calendarId: "primary",
    timeMin: `${dateOnly}T00:00:00+09:00`,
    timeMax: `${nextDay(dateOnly)}T00:00:00+09:00`,
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

export async function updateGoogleCalendarEvent(
  oldName: string,
  oldDateStart: string,
  updates: { name?: string; dateStart?: string; dateEnd?: string; place?: string; description?: string },
): Promise<GCalResult> {
  const auth = await getAuthorizedClient();
  if (!auth) {
    return { success: false, message: "Google Calendar not configured." };
  }

  const found = await findGoogleCalendarEvent(oldName, oldDateStart);
  if (!found.exists || !found.eventId) {
    return { success: false, message: "Google Calendar에서 해당 이벤트를 찾을 수 없습니다." };
  }

  const calendar = google.calendar({ version: "v3", auth });
  const patch: calendar_v3.Schema$Event = {};

  if (updates.name) patch.summary = updates.name;
  if (updates.place) patch.location = updates.place;
  if (updates.description) patch.description = updates.description;
  if (updates.dateStart) {
    const timing = buildEventTiming(updates.dateStart, updates.dateEnd);
    patch.start = timing.start;
    patch.end = timing.end;
  } else if (updates.dateEnd) {
    const existing = await calendar.events.get({ calendarId: "primary", eventId: found.eventId });
    const existingStart = existing.data.start?.dateTime ?? existing.data.start?.date ?? oldDateStart;
    const timing = buildEventTiming(existingStart, updates.dateEnd);
    patch.start = timing.start;
    patch.end = timing.end;
  }

  const res = await calendar.events.patch({
    calendarId: "primary",
    eventId: found.eventId,
    requestBody: patch,
  });

  return {
    success: true,
    message: "Google Calendar 이벤트가 수정되었습니다.",
    eventId: res.data.id ?? undefined,
    eventUrl: res.data.htmlLink ?? undefined,
  };
}

function nextDay(dateStr: string): string {
  const [year, month, day] = dateStr.split("-").map(Number);
  const d = new Date(year, month - 1, day + 1);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${dd}`;
}
