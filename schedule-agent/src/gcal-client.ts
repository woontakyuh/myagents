export interface GCalResult {
  success: boolean;
  message: string;
}

export interface GCalEventInput {
  name: string;
  dateStart: string;
  dateEnd?: string;
  place?: string;
}

export async function createGoogleCalendarEvent(_input: GCalEventInput): Promise<GCalResult> {
  // TODO: Implement Google Calendar OAuth2 flow and event insertion.
  // Steps:
  // 1) Enable Google Calendar API in GCP and create OAuth client credentials.
  // 2) Store and refresh OAuth tokens securely.
  // 3) Call Google Calendar events.insert with schedule details.
  return {
    success: false,
    message: "Google Calendar not configured. Enable Calendar API and set up OAuth2.",
  };
}
