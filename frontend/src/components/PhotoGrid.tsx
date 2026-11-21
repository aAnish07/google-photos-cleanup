import { ChevronLeft, ChevronRight, ImageOff } from "lucide-react";
import type { Photo, PhotoPage } from "../types";
import PhotoCard from "./PhotoCard";

interface Props {
  data?: PhotoPage;
  isLoading: boolean;
  selected: Set<string>;
  onToggle: (id: string) => void;
  onOpen: (photo: Photo) => void;
  page: number;
  onPage: (p: number) => void;
}

export default function PhotoGrid({
  data,
  isLoading,
  selected,
  onToggle,
  onOpen,
  page,
  onPage,
}: Props) {
  if (isLoading && !data) {
    return (
      <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {Array.from({ length: 15 }).map((_, i) => (
          <div
            key={i}
            className="aspect-square animate-pulse rounded-lg bg-slate-200"
          />
        ))}
      </div>
    );
  }

  if (!data || data.photos.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center text-slate-400">
        <ImageOff className="mb-2 h-10 w-10" />
        <p>No photos match these filters.</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="grid flex-1 grid-cols-2 gap-3 p-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {data.photos.map((photo) => (
          <PhotoCard
            key={photo.id}
            photo={photo}
            selected={selected.has(photo.id)}
            onToggle={() => onToggle(photo.id)}
            onOpen={() => onOpen(photo)}
          />
        ))}
      </div>

      <div className="flex items-center justify-center gap-4 border-t border-slate-200 py-3 text-sm">
        <button
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="flex items-center gap-1 rounded-md px-3 py-1 text-slate-600 hover:bg-slate-100 disabled:opacity-40"
        >
          <ChevronLeft className="h-4 w-4" /> Prev
        </button>
        <span className="text-slate-500">
          Page {data.page} of {data.total_pages || 1} · {data.total.toLocaleString()}{" "}
          photos
        </span>
        <button
          disabled={page >= data.total_pages}
          onClick={() => onPage(page + 1)}
          className="flex items-center gap-1 rounded-md px-3 py-1 text-slate-600 hover:bg-slate-100 disabled:opacity-40"
        >
          Next <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
