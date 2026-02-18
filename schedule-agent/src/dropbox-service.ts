import { existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const DEFAULT_BASE_PATH = "Library/CloudStorage/Dropbox/Tak/2. 학회";

export interface FolderCreationResult {
  path: string;
  existed: boolean;
}

export class DropboxService {
  private readonly basePath: string;

  public constructor(basePath?: string) {
    const home = process.env.HOME;
    if (!home) {
      throw new Error("HOME environment variable is missing");
    }

    this.basePath = basePath ?? join(home, DEFAULT_BASE_PATH);
  }

  public createEventFolder(name: string, date: string): FolderCreationResult {
    this.validateDate(date);

    const year = date.slice(0, 4);
    const safeName = this.sanitizeName(name);
    const fullPath = join(this.basePath, year, `${date} ${safeName}`);

    const existed = existsSync(fullPath);
    mkdirSync(fullPath, { recursive: true });

    return {
      path: fullPath,
      existed,
    };
  }

  private validateDate(date: string): void {
    if (!/^\d{4}-\d{2}-\d{2}$/u.test(date)) {
      throw new Error("date must be in yyyy-mm-dd format");
    }
  }

  private sanitizeName(name: string): string {
    return name.trim().replace(/[/:]/gu, "-");
  }
}
