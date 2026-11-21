import { useState } from "react";
import { Loader2, Trash2, Undo2, X } from "lucide-react";
import { formatBytes } from "../types";

interface Props {
  selectedCount: number;
  selectedSizeBytes: number;
  filterTotal: number;
  busy: boolean;
  undoAvailable: boolean;
  onClear: () => void;
  onTrashSelected: () => void;
  onTrashByFilter: () => void;
  onUndo: () => void;
}

export default function BulkActions({
  selectedCount,
  selectedSizeBytes,
  filterTotal,
  busy,
  undoAvailable,
  onClear,
  onTrashSelected,
  onTrashByFilter,
  onUndo,
}: Props) {
  const [confirm, setConfirm] = useState(false);

  if (selectedCount === 0 && !undoAvailable) return null;

  return (
    <>
      <div className="sticky bottom-0 z-20 flex items-center justify-between border-t border-slate-200 bg-white/95 px-4 py-3 shadow-[0_-2px_8px_rgba(0,0,0,0.05)] backdrop-blur">
        <div className="flex items-center gap-3 text-sm">
          {selectedCount > 0 ? (
            <>
              <button
                onClick={onClear}
                className="flex items-center gap-1 text-slate-500 hover:text-slate-800"
              >
                <X className="h-4 w-4" /> Clear
              </button>
              <span className="font-medium text-slate-700">
                {selectedCount.toLocaleString()} selected ·{" "}
                {formatBytes(selectedSizeBytes)}
              </span>
              {filterTotal > selectedCount && (
                <button
                  onClick={onTrashByFilter}
                  className="text-blue-600 hover:underline"
                >
                  Trash all {filterTotal.toLocaleString()} matching filter
                </button>
              )}
            </>
          ) : (
            <span className="text-slate-400">No selection</span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {undoAvailable && (
            <button
              onClick={onUndo}
              disabled={busy}
              className="flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              <Undo2 className="h-4 w-4" /> Undo last trash
            </button>
          )}
          {selectedCount > 0 && (
            <button
              onClick={() => setConfirm(true)}
              disabled={busy}
              className="flex items-center gap-1.5 rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              Move {selectedCount.toLocaleString()} to Trash
            </button>
          )}
        </div>
      </div>

      {confirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setConfirm(false)}
        >
          <div
            className="w-full max-w-md rounded-xl bg-white p-5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-slate-800">
              Move {selectedCount.toLocaleString()} photos to Trash?
            </h3>
            <p className="mt-2 text-sm text-slate-600">
              These {selectedCount.toLocaleString()} photos (
              {formatBytes(selectedSizeBytes)}) will be moved to your Google
              Drive trash. You have <strong>30 days</strong> to restore them
              before Google deletes them permanently.
            </p>
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={() => setConfirm(false)}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setConfirm(false);
                  onTrashSelected();
                }}
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                Move to Trash
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
