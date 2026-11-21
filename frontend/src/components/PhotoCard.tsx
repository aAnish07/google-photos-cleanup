import { Check, Play } from "lucide-react";
import {
  formatBytes,
  KEEP_SIGNAL_COLORS,
  Photo,
  prettyLabel,
} from "../types";

interface Props {
  photo: Photo;
  selected: boolean;
  onToggle: () => void;
  onOpen: () => void;
}

export default function PhotoCard({ photo, selected, onToggle, onOpen }: Props) {
  const colors = photo.keep_signal
    ? KEEP_SIGNAL_COLORS[photo.keep_signal]
    : undefined;
  const date = photo.created_time
    ? new Date(photo.created_time).toLocaleDateString()
    : "";
  const isVideo = (photo.mime_type ?? "").startsWith("video/");

  return (
    <div
      className={`group relative overflow-hidden rounded-lg border-2 bg-white shadow-sm transition ${
        selected ? "border-blue-500 ring-2 ring-blue-200" : colors?.border ?? "border-slate-200"
      }`}
    >
      {/* Selection checkbox */}
      <button
        onClick={onToggle}
        aria-label={selected ? "Deselect" : "Select"}
        className={`absolute left-2 top-2 z-10 flex h-6 w-6 items-center justify-center rounded-md border-2 transition ${
          selected
            ? "border-blue-500 bg-blue-500 text-white"
            : "border-white/80 bg-black/20 text-transparent group-hover:border-white"
        }`}
      >
        <Check className="h-4 w-4" />
      </button>

      {colors && (
        <span
          className={`absolute right-2 top-2 z-10 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${colors.badge}`}
        >
          {colors.label}
        </span>
      )}

      <button
        onClick={onOpen}
        className="relative block aspect-square w-full bg-slate-100"
      >
        <img
          src={`/api/photos/${photo.id}/image`}
          alt={photo.name}
          loading="lazy"
          className="h-full w-full object-cover"
          onError={(e) => {
            (e.target as HTMLImageElement).style.visibility = "hidden";
          }}
        />
        {isVideo && (
          <span className="pointer-events-none absolute bottom-2 left-2 flex items-center gap-1 rounded bg-black/60 px-1.5 py-0.5 text-[10px] font-medium text-white">
            <Play className="h-3 w-3 fill-white" /> Video
          </span>
        )}
      </button>

      <div className="px-2 py-1.5">
        <div className="truncate text-xs font-medium text-slate-700" title={photo.name}>
          {prettyLabel(photo.photo_type)}
        </div>
        <div className="flex items-center justify-between text-[11px] text-slate-400">
          <span>{date}</span>
          <span>{formatBytes(photo.size_bytes)}</span>
        </div>
      </div>
    </div>
  );
}
