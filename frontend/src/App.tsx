import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CloudOff, Images } from "lucide-react";
import { client } from "./api/client";
import { useAuthStatus } from "./hooks/useScan";
import { usePhotos } from "./hooks/usePhotos";
import {
  EMPTY_FILTERS,
  Filters,
  formatBytes,
  Photo,
} from "./types";
import BulkActions from "./components/BulkActions";
import FilterBar from "./components/FilterBar";
import PhotoGrid from "./components/PhotoGrid";
import PhotoPreview from "./components/PhotoPreview";
import ScanProgress from "./components/ScanProgress";
import StatsPanel from "./components/StatsPanel";

const PER_PAGE = 50;

function hasActiveFilters(f: Filters): boolean {
  return (
    f.photo_type.length > 0 ||
    f.keep_signal.length > 0 ||
    f.quality_signal.length > 0 ||
    f.has_text !== "" ||
    !!f.date_from ||
    !!f.date_to ||
    f.min_size != null ||
    f.min_confidence > 0
  );
}

export default function App() {
  const qc = useQueryClient();
  const { data: auth } = useAuthStatus();
  const authed = !!auth?.authenticated;

  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [sizeMap, setSizeMap] = useState<Map<string, number>>(new Map());
  const [previewIndex, setPreviewIndex] = useState<number | null>(null);
  const [undoAvailable, setUndoAvailable] = useState(false);
  const [filterConfirm, setFilterConfirm] = useState<{
    count: number;
    size: number;
    token: string;
  } | null>(null);

  const { data, isLoading, isFetching } = usePhotos(filters, page, PER_PAGE);

  // Reset to page 1 when filters change.
  useEffect(() => setPage(1), [filters]);

  // Keep a running id -> size map so selection size survives pagination.
  useEffect(() => {
    if (!data) return;
    setSizeMap((prev) => {
      const next = new Map(prev);
      for (const p of data.photos) next.set(p.id, p.size_bytes ?? 0);
      return next;
    });
  }, [data]);

  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ["photos"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
  };

  const trashSelected = useMutation({
    mutationFn: () => client.trash([...selected]),
    onSuccess: () => {
      setSelected(new Set());
      setUndoAvailable(true);
      invalidateAll();
    },
  });

  const undo = useMutation({
    mutationFn: () => client.undo(),
    onSuccess: () => {
      setUndoAvailable(false);
      invalidateAll();
    },
  });

  const trashOne = useMutation({
    mutationFn: (id: string) => client.trash([id]),
    onSuccess: () => {
      setUndoAvailable(true);
      invalidateAll();
    },
  });

  const selectAllMatching = useMutation({
    mutationFn: () => client.photoIds(filters),
    onSuccess: (res) => {
      setSelected(new Set(res.items.map((i) => i.id)));
      setSizeMap((prev) => {
        const next = new Map(prev);
        for (const i of res.items) next.set(i.id, i.size_bytes ?? 0);
        return next;
      });
    },
  });

  const trashByFilter = useMutation({
    mutationFn: (token?: string) => client.trashByFilter(filters, token),
    onSuccess: (res) => {
      if (res.requires_confirmation) {
        setFilterConfirm({
          count: res.count,
          size: res.total_size_bytes ?? 0,
          token: res.confirm_token!,
        });
      } else {
        setFilterConfirm(null);
        setSelected(new Set());
        setUndoAvailable(true);
        invalidateAll();
      }
    },
  });

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const selectedSize = useMemo(
    () => [...selected].reduce((sum, id) => sum + (sizeMap.get(id) ?? 0), 0),
    [selected, sizeMap]
  );

  const previewPhoto: Photo | null =
    previewIndex != null && data ? data.photos[previewIndex] ?? null : null;

  const navigate = (dir: -1 | 1) => {
    if (previewIndex == null || !data) return;
    const next = previewIndex + dir;
    if (next >= 0 && next < data.photos.length) setPreviewIndex(next);
  };

  const busy =
    trashSelected.isPending ||
    undo.isPending ||
    trashOne.isPending ||
    trashByFilter.isPending;

  return (
    <div className="flex h-screen flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3">
        <div className="flex items-center gap-2">
          <Images className="h-6 w-6 text-blue-600" />
          <h1 className="text-lg font-semibold text-slate-800">
            Google Photos Clean-Up
          </h1>
        </div>
        <div className="flex items-center gap-4">
          {!authed && (
            <a
              href="/auth/login"
              className="flex items-center gap-1.5 rounded-md bg-slate-800 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-900"
            >
              <CloudOff className="h-4 w-4" /> Connect Google Drive
            </a>
          )}
          <ScanProgress authed={authed} />
        </div>
      </header>

      {!authed && (
        <div className="bg-amber-50 px-5 py-2 text-sm text-amber-800">
          Connect your Google Drive to scan and classify your photos.
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        {/* Filter sidebar */}
        <aside className="w-64 shrink-0 border-r border-slate-200 bg-white">
          <FilterBar filters={filters} onChange={setFilters} />
        </aside>

        {/* Main content */}
        <main className="flex min-w-0 flex-1 flex-col">
          <div className="border-b border-slate-200 bg-slate-50 p-4">
            <StatsPanel />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <PhotoGrid
              data={data}
              isLoading={isLoading || (isFetching && !data)}
              selected={selected}
              onToggle={toggle}
              onOpen={(p) =>
                setPreviewIndex(data?.photos.findIndex((x) => x.id === p.id) ?? null)
              }
              page={page}
              onPage={setPage}
            />
          </div>
          <BulkActions
            selectedCount={selected.size}
            selectedSizeBytes={selectedSize}
            filterTotal={data?.total ?? 0}
            hasActiveFilters={hasActiveFilters(filters)}
            busy={busy}
            selectAllBusy={selectAllMatching.isPending}
            undoAvailable={undoAvailable}
            onClear={() => setSelected(new Set())}
            onSelectAllMatching={() => selectAllMatching.mutate()}
            onTrashSelected={() => trashSelected.mutate()}
            onTrashByFilter={() => trashByFilter.mutate(undefined)}
            onUndo={() => undo.mutate()}
          />
        </main>
      </div>

      {/* Preview modal */}
      {previewPhoto && (
        <PhotoPreview
          photo={previewPhoto}
          onClose={() => setPreviewIndex(null)}
          onTrash={(id) => {
            trashOne.mutate(id);
            setPreviewIndex(null);
          }}
          onNavigate={navigate}
        />
      )}

      {/* Trash-by-filter confirmation */}
      {filterConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setFilterConfirm(null)}
        >
          <div
            className="w-full max-w-md rounded-xl bg-white p-5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-slate-800">
              Trash all {filterConfirm.count.toLocaleString()} matching photos?
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              Every photo matching the current filter (
              {filterConfirm.count.toLocaleString()} photos,{" "}
              {formatBytes(filterConfirm.size)}) will be moved to Google Drive
              trash. You have <strong>30 days</strong> to undo.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setFilterConfirm(null)}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={() => trashByFilter.mutate(filterConfirm.token)}
                disabled={busy}
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                Trash {filterConfirm.count.toLocaleString()} photos
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
