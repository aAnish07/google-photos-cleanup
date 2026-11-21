export type ClassificationStatus = "pending" | "classified" | "failed";

export interface Photo {
  id: string;
  name: string;
  mime_type: string | null;
  size_bytes: number | null;
  created_time: string | null;
  modified_time: string | null;
  thumbnail_path: string | null;
  thumbnail_url: string | null;
  web_view_link: string | null;
  photo_type: string | null;
  photo_type_confidence: number | null;
  keep_signal: string | null;
  keep_signal_confidence: number | null;
  has_text: string | null;
  has_text_confidence: number | null;
  quality_signal: string | null;
  quality_signal_confidence: number | null;
  classification_status: ClassificationStatus;
  classification_error: string | null;
  classified_at: string | null;
  trashed: number;
  trashed_at: string | null;
  scan_batch: string | null;
}

export interface PhotoPage {
  photos: Photo[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface GroupStat {
  count: number;
  size_bytes: number;
}

export interface Stats {
  total_photos: number;
  total_size_bytes: number;
  estimated_recoverable_bytes: number;
  failed_count: number;
  by_type: Record<string, GroupStat>;
  by_keep_signal: Record<string, GroupStat>;
  by_quality: Record<string, GroupStat>;
  by_year_month: Record<string, GroupStat>;
}

export interface ScanRun {
  id: string;
  started_at: string | null;
  completed_at: string | null;
  status: "running" | "completed" | "failed" | "cancelled";
  total_files: number;
  classified: number;
  failed: number;
  next_page_token: string | null;
}

export interface ScanStatus {
  running: boolean;
  current_scan_id: string | null;
  latest: ScanRun | null;
}

export interface Filters {
  photo_type: string[];
  keep_signal: string[];
  quality_signal: string[];
  has_text: "" | "yes" | "no";
  date_from: string;
  date_to: string;
  min_size: number | null;
  min_confidence: number;
  sort: "created_time" | "size_bytes" | "photo_type_confidence";
  order: "asc" | "desc";
}

export const EMPTY_FILTERS: Filters = {
  photo_type: [],
  keep_signal: [],
  quality_signal: [],
  has_text: "",
  date_from: "",
  date_to: "",
  min_size: null,
  min_confidence: 0,
  sort: "created_time",
  order: "desc",
};

// Option metadata (keys mirror the backend classifier criteria).
export const PHOTO_TYPES = [
  "screenshot",
  "scenery_landscape",
  "people_portrait",
  "selfie",
  "food_drink",
  "document_text",
  "meme_funny",
  "receipt_bill",
  "pet_animal",
  "artwork_design",
  "event_celebration",
  "travel_landmark",
  "product_shopping",
  "vehicle",
  "interior_exterior",
  "other",
] as const;

export const KEEP_SIGNALS = [
  "definitely_keep",
  "maybe_keep",
  "likely_delete",
  "definitely_delete",
] as const;

export const QUALITY_SIGNALS = ["high", "medium", "low", "blurry"] as const;

export const KEEP_SIGNAL_COLORS: Record<
  string,
  { badge: string; border: string; dot: string; label: string }
> = {
  definitely_keep: {
    badge: "bg-green-100 text-green-800",
    border: "border-green-400",
    dot: "bg-green-500",
    label: "Definitely keep",
  },
  maybe_keep: {
    badge: "bg-yellow-100 text-yellow-800",
    border: "border-yellow-400",
    dot: "bg-yellow-500",
    label: "Maybe keep",
  },
  likely_delete: {
    badge: "bg-orange-100 text-orange-800",
    border: "border-orange-400",
    dot: "bg-orange-500",
    label: "Likely delete",
  },
  definitely_delete: {
    badge: "bg-red-100 text-red-800",
    border: "border-red-400",
    dot: "bg-red-500",
    label: "Definitely delete",
  },
};

export function prettyLabel(value: string | null): string {
  if (!value) return "—";
  return value
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}
