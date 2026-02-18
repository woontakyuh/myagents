import { AppConfig } from "./config.js";

const NOTION_API_BASE = "https://api.notion.com/v1";

interface NotionText {
  plain_text?: string;
  text?: { content?: string };
}

interface NotionDate {
  start: string;
  end: string | null;
}

interface NotionSelect {
  name: string;
}

interface NotionProperty {
  type: string;
  title?: NotionText[];
  rich_text?: NotionText[];
  date?: NotionDate | null;
  select?: NotionSelect | null;
  multi_select?: NotionSelect[];
  url?: string | null;
  checkbox?: boolean;
  number?: number | null;
  email?: string | null;
  phone_number?: string | null;
  status?: NotionSelect | null;
}

interface NotionPage {
  id: string;
  url: string;
  last_edited_time: string;
  properties: Record<string, NotionProperty>;
}

interface NotionQueryResponse {
  results: NotionPage[];
}

interface NotionErrorResponse {
  object?: string;
  status?: number;
  code?: string;
  message?: string;
}

export interface ListSchedulesParams {
  status?: string;
  from_date?: string;
  to_date?: string;
  category?: string;
  limit?: number;
}

export interface ScheduleMutationInput {
  name?: string;
  date_start?: string;
  date_end?: string;
  place?: string;
  category?: string;
  society?: string[];
  status?: string;
  topic?: string;
  link?: string;
  abstract_deadline?: string;
}

export interface ScheduleListItem {
  page_id: string;
  url: string;
  name: string;
  date_start: string | null;
  date_end: string | null;
  place: string;
  category: string;
  status: string;
}

export interface SchedulePageDetails {
  page_id: string;
  url: string;
  last_edited_time: string;
  properties: Record<string, unknown>;
}

export class NotionScheduleClient {
  private readonly token: string;
  private readonly databaseId: string;
  private readonly notionVersion: string;

  public constructor(config: AppConfig) {
    this.token = config.notionToken;
    this.databaseId = config.notionDatabaseId;
    this.notionVersion = config.notionApiVersion;
  }

  public async listSchedules(params: ListSchedulesParams): Promise<ScheduleListItem[]> {
    const filters: Array<Record<string, unknown>> = [];

    if (params.status) {
      filters.push({ property: "준비 상태", select: { equals: params.status } });
    }
    if (params.category) {
      filters.push({ property: "분류", select: { equals: params.category } });
    }
    if (params.from_date) {
      filters.push({ property: "Date", date: { on_or_after: params.from_date } });
    }
    if (params.to_date) {
      filters.push({ property: "Date", date: { on_or_before: params.to_date } });
    }

    const body: Record<string, unknown> = {
      sorts: [{ property: "Date", direction: "descending" }],
      page_size: params.limit ?? 20,
    };

    if (filters.length === 1) {
      body.filter = filters[0];
    } else if (filters.length > 1) {
      body.filter = { and: filters };
    }

    const response = await this.request<NotionQueryResponse>(
      `/databases/${this.databaseId}/query`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    );

    return response.results.map((page) => this.toScheduleListItem(page));
  }

  public async searchSchedules(query: string, limit: number = 20): Promise<ScheduleListItem[]> {
    const response = await this.request<NotionQueryResponse>(
      `/databases/${this.databaseId}/query`,
      {
        method: "POST",
        body: JSON.stringify({
          filter: {
            property: "Name",
            title: { contains: query },
          },
          sorts: [{ property: "Date", direction: "descending" }],
          page_size: limit,
        }),
      },
    );

    return response.results.map((page) => this.toScheduleListItem(page));
  }

  public async getSchedule(pageId: string): Promise<SchedulePageDetails> {
    const page = await this.request<NotionPage>(`/pages/${pageId}`, {
      method: "GET",
    });

    return {
      page_id: page.id,
      url: page.url,
      last_edited_time: page.last_edited_time,
      properties: this.extractProperties(page.properties),
    };
  }

  public async addSchedule(input: ScheduleMutationInput): Promise<SchedulePageDetails> {
    if (!input.name) {
      throw new Error("name is required");
    }
    if (!input.date_start) {
      throw new Error("date_start is required");
    }

    if (input.date_end && !input.date_start) {
      throw new Error("date_start must be set when date_end is provided");
    }

    const page = await this.request<NotionPage>("/pages", {
      method: "POST",
      body: JSON.stringify({
        parent: { database_id: this.databaseId },
        properties: this.buildProperties(input, true),
      }),
    });

    return {
      page_id: page.id,
      url: page.url,
      last_edited_time: page.last_edited_time,
      properties: this.extractProperties(page.properties),
    };
  }

  public async updateSchedule(pageId: string, input: ScheduleMutationInput): Promise<SchedulePageDetails> {
    if (input.date_end && !input.date_start) {
      throw new Error("date_start must be set when date_end is provided");
    }

    const properties = this.buildProperties(input, false);

    if (Object.keys(properties).length === 0) {
      throw new Error("At least one updatable field is required");
    }

    const page = await this.request<NotionPage>(`/pages/${pageId}`, {
      method: "PATCH",
      body: JSON.stringify({ properties }),
    });

    return {
      page_id: page.id,
      url: page.url,
      last_edited_time: page.last_edited_time,
      properties: this.extractProperties(page.properties),
    };
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const response = await fetch(`${NOTION_API_BASE}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${this.token}`,
        "Notion-Version": this.notionVersion,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      const errorBody = (await response.json().catch(() => ({}))) as NotionErrorResponse;
      const message = errorBody.message ?? `Notion request failed with ${response.status}`;
      throw new Error(message);
    }

    return (await response.json()) as T;
  }

  private buildProperties(input: ScheduleMutationInput, requireNameAndDate: boolean): Record<string, unknown> {
    const properties: Record<string, unknown> = {};

    if (input.name) {
      properties.Name = {
        title: [{ text: { content: input.name } }],
      };
    } else if (requireNameAndDate) {
      throw new Error("name is required");
    }

    if (input.date_start) {
      properties.Date = {
        date: {
          start: input.date_start,
          end: input.date_end ?? null,
        },
      };
    } else if (requireNameAndDate) {
      throw new Error("date_start is required");
    }

    if (input.place !== undefined) {
      properties.Place = {
        rich_text: input.place
          ? [{ text: { content: input.place } }]
          : [],
      };
    }
    if (input.category !== undefined) {
      properties["분류"] = {
        select: input.category ? { name: input.category } : null,
      };
    }
    if (input.society !== undefined) {
      properties["학회명"] = {
        multi_select: input.society.map((name) => ({ name })),
      };
    }
    if (input.status !== undefined) {
      properties["준비 상태"] = {
        select: input.status ? { name: input.status } : null,
      };
    }
    if (input.topic !== undefined) {
      properties["발표 주제"] = {
        rich_text: input.topic
          ? [{ text: { content: input.topic } }]
          : [],
      };
    }
    if (input.link !== undefined) {
      properties.Link = {
        url: input.link || null,
      };
    }
    if (input.abstract_deadline !== undefined) {
      properties["초록 제출 기한"] = {
        date: input.abstract_deadline ? { start: input.abstract_deadline, end: null } : null,
      };
    }

    return properties;
  }

  private toScheduleListItem(page: NotionPage): ScheduleListItem {
    const props = page.properties;

    const dateProperty = props.Date;
    const dateStart = dateProperty?.type === "date" ? dateProperty.date?.start ?? null : null;
    const dateEnd = dateProperty?.type === "date" ? dateProperty.date?.end ?? null : null;

    return {
      page_id: page.id,
      url: page.url,
      name: this.getTitle(props.Name),
      date_start: dateStart,
      date_end: dateEnd,
      place: this.getRichText(props.Place),
      status: this.getSelectName(props["준비 상태"]),
      category: this.getSelectName(props["분류"]),
    };
  }

  private extractProperties(properties: Record<string, NotionProperty>): Record<string, unknown> {
    const output: Record<string, unknown> = {};

    for (const [name, value] of Object.entries(properties)) {
      output[name] = this.getPropertyValue(value);
    }

    return output;
  }

  private getPropertyValue(property: NotionProperty): unknown {
    switch (property.type) {
      case "title":
        return (property.title ?? []).map((item: NotionText) => item.plain_text ?? item.text?.content ?? "").join("");
      case "rich_text":
        return (property.rich_text ?? [])
          .map((item: NotionText) => item.plain_text ?? item.text?.content ?? "")
          .join("");
      case "date":
        return property.date ?? null;
      case "select":
        return property.select?.name ?? null;
      case "multi_select":
        return (property.multi_select ?? []).map((option: NotionSelect) => option.name);
      case "url":
        return property.url ?? null;
      case "checkbox":
        return property.checkbox ?? false;
      case "number":
        return property.number ?? null;
      case "email":
        return property.email ?? null;
      case "phone_number":
        return property.phone_number ?? null;
      case "status":
        return property.status?.name ?? null;
      default:
        return null;
    }
  }

  private getTitle(property: NotionProperty | undefined): string {
    if (!property || property.type !== "title") {
      return "";
    }
    return (property.title ?? [])
      .map((item: NotionText) => item.plain_text ?? item.text?.content ?? "")
      .join("")
      .trim();
  }

  private getRichText(property: NotionProperty | undefined): string {
    if (!property || property.type !== "rich_text") {
      return "";
    }
    return (property.rich_text ?? [])
      .map((item: NotionText) => item.plain_text ?? item.text?.content ?? "")
      .join("")
      .trim();
  }

  private getSelectName(property: NotionProperty | undefined): string {
    if (!property || property.type !== "select") {
      return "";
    }
    return property.select?.name ?? "";
  }
}
