import axios from "axios";
import type { Filters, PhotoPage, ScanStatus, Stats } from "../types";

const api = axios.create({ baseURL: "/" });

function filtersToParams(filters: Filters, page: number, perPage: number) {
  const p: Record<string, string | number> = {
    page,
    per_page: perPage,
    sort: filters.sort,
    order: filters.order,
    trashed: "false",
  };
  if (filters.photo_type.length) p.photo_type = filters.photo_type.join(",");
  if (filters.keep_signal.length) p.keep_signal = filters.keep_signal.join(",");
  if (filters.quality_signal.length)
    p.quality_signal = filters.quality_signal.join(",");
  if (filters.has_text) p.has_text = filters.has_text;
  if (filters.date_from) p.date_from = filters.date_from;
  if (filters.date_to) p.date_to = filters.date_to;
  if (filters.min_size) p.min_size = filters.min_size;
  if (filters.min_confidence > 0) p.min_confidence = filters.min_confidence;
  return p;
}

// Params for trash-by-filter (no pagination / sort).
export function filtersToTrashBody(filters: Filters, confirmToken?: string) {
  const body: Record<string, unknown> = {};
  if (filters.photo_type.length) body.photo_type = filters.photo_type.join(",");
  if (filters.keep_signal.length)
    body.keep_signal = filters.keep_signal.join(",");
  if (filters.quality_signal.length)
    body.quality_signal = filters.quality_signal.join(",");
  if (filters.has_text) body.has_text = filters.has_text;
  if (filters.date_from) body.date_from = filters.date_from;
  if (filters.date_to) body.date_to = filters.date_to;
  if (filters.min_size) body.min_size = filters.min_size;
  if (filters.min_confidence > 0) body.min_confidence = filters.min_confidence;
  if (confirmToken) body.confirm_token = confirmToken;
  return body;
}

export const client = {
  async health() {
    const { data } = await api.get("/api/health");
    return data as { status: string; classifier_backend: string };
  },

  async authStatus() {
    const { data } = await api.get("/auth/status");
    return data as { authenticated: boolean };
  },

  async photos(filters: Filters, page: number, perPage: number) {
    const { data } = await api.get("/api/photos", {
      params: filtersToParams(filters, page, perPage),
    });
    return data as PhotoPage;
  },

  async stats() {
    const { data } = await api.get("/api/stats");
    return data as Stats;
  },

  async scanStatus() {
    const { data } = await api.get("/api/scan/status");
    return data as ScanStatus;
  },

  async startScan() {
    const { data } = await api.post("/api/scan/start");
    return data as { scan_id: string; resumed: boolean };
  },

  async cancelScan() {
    const { data } = await api.post("/api/scan/cancel");
    return data;
  },

  async librarySize() {
    const { data } = await api.get("/api/scan/library-size");
    return data as { count: number; total_size_bytes: number };
  },

  async trash(fileIds: string[]) {
    const { data } = await api.post("/api/trash", { file_ids: fileIds });
    return data as { succeeded: string[]; failed: unknown[] };
  },

  async undo(fileIds?: string[]) {
    const { data } = await api.post("/api/trash/undo", {
      file_ids: fileIds ?? [],
    });
    return data as { succeeded: string[]; failed: unknown[] };
  },

  async trashByFilter(filters: Filters, confirmToken?: string) {
    const { data } = await api.post(
      "/api/trash/by-filter",
      filtersToTrashBody(filters, confirmToken)
    );
    return data as {
      requires_confirmation?: boolean;
      count: number;
      total_size_bytes?: number;
      confirm_token?: string;
      succeeded?: string[];
      failed?: unknown[];
    };
  },
};
