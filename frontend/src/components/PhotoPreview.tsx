import { useEffect } from "react";
import {
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Trash2,
  X,
} from "lucide-react";
import {
  formatBytes,
  KEEP_SIGNAL_COLORS,
  Photo,
  prettyLabel,
} from "../types";

interface Props {
  photo: Photo;
  onClose: () => void;
  onTrash: (id: string) => void;
  onNavigate: (dir: -1 | 1) => void;
}

function ConfidenceRow({
  label,
  value,
  confidence,
}: {
  label: string;
  value: string | null;
  confidence: number | null;
}) {
  const pct = confidence != null ? Math.round(confidence * 100) : 0;
  return (
    <div className="py-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-500">{label}</span>
        <span className="font-medium text-slate-800">{prettyLabel(value)}</span>
      </div>
      <div className="mt-1 flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full bg-slate-400" style={{ width: `${pct}%` }} />
        </div>
        <span className="w-9 text-right text-xs text-slate-400">
          {confidence != null ? `${pct}%` : "—"}
        </span>
      </div>
    </div>
  );
}

export default function PhotoPreview({
  photo,
  onClose,
  onTrash,
  onNavigate,
}: Props) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") onNavigate(-1);
      if (e.key === "ArrowRight") onNavigate(1);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, onNavigate]);

  const colors = photo.keep_signal
    ? KEEP_SIGNAL_COLORS[photo.keep_signal]
    : undefined;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <button
        onClick={(e) => {
          e.stopPropagation();
          onNavigate(-1);
        }}
        className="absolute left-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
      >
        <ChevronLeft className="h-6 w-6" />
      </button>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onNavigate(1);
        }}
        className="absolute right-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
      >
        <ChevronRight className="h-6 w-6" />
      </button>

      <div
        className="flex max-h-[90vh] w-full max-w-4xl overflow-hidden rounded-xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-1 items-center justify-center bg-slate-900">
          <img
            src={`/api/photos/${photo.id}/image`}
            alt={photo.name}
            className="max-h-[90vh] w-full object-contain"
          />
        </div>

        <div className="flex w-80 flex-col border-l border-slate-200">
          <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
            <span className="truncate text-sm font-medium" title={photo.name}>
              {photo.name}
            </span>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-2">
            {colors && (
              <span
                className={`mb-2 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors.badge}`}
              >
                {colors.label}
              </span>
            )}

            <ConfidenceRow
              label="Type"
              value={photo.photo_type}
              confidence={photo.photo_type_confidence}
            />
            <ConfidenceRow
              label="Keep signal"
              value={photo.keep_signal}
              confidence={photo.keep_signal_confidence}
            />
            <ConfidenceRow
              label="Has text"
              value={photo.has_text}
              confidence={photo.has_text_confidence}
            />
            <ConfidenceRow
              label="Quality"
              value={photo.quality_signal}
              confidence={photo.quality_signal_confidence}
            />

            <div className="mt-3 space-y-1 border-t border-slate-100 pt-3 text-xs text-slate-500">
              <div className="flex justify-between">
                <span>Size</span>
                <span>{formatBytes(photo.size_bytes)}</span>
              </div>
              <div className="flex justify-between">
                <span>Created</span>
                <span>
                  {photo.created_time
                    ? new Date(photo.created_time).toLocaleString()
                    : "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span>Status</span>
                <span>{photo.classification_status}</span>
              </div>
            </div>
          </div>

          <div className="space-y-2 border-t border-slate-200 p-3">
            {photo.web_view_link && (
              <a
                href={photo.web_view_link}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-center gap-1.5 rounded-md border border-slate-300 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
              >
                <ExternalLink className="h-4 w-4" /> Open in Drive
              </a>
            )}
            <button
              onClick={() => onTrash(photo.id)}
              className="flex w-full items-center justify-center gap-1.5 rounded-md bg-red-600 py-1.5 text-sm font-medium text-white hover:bg-red-700"
            >
              <Trash2 className="h-4 w-4" /> Move to Trash
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
