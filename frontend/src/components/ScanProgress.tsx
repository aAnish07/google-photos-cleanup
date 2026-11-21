import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Loader2, Play, RefreshCw, StopCircle } from "lucide-react";
import { client } from "../api/client";
import { useScan } from "../hooks/useScan";
import { useStats } from "../hooks/usePhotos";

export default function ScanProgress({ authed }: { authed: boolean }) {
  const { data } = useScan();
  const { data: stats } = useStats();
  const qc = useQueryClient();

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["scan-status"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["photos"] });
  };

  const start = useMutation({
    mutationFn: () => client.startScan(),
    onSuccess: invalidate,
  });
  const cancel = useMutation({
    mutationFn: () => client.cancelScan(),
    onSuccess: invalidate,
  });
  const retry = useMutation({
    mutationFn: () => client.retryFailed(),
    onSuccess: invalidate,
  });

  const failedCount = stats?.failed_count ?? 0;

  const running = data?.running;
  const latest = data?.latest;

  if (running && latest) {
    const total = latest.total_files || 0;
    const done = latest.classified + latest.failed;
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    return (
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
          <span>
            Scanning… {latest.classified.toLocaleString()} classified
            {latest.failed > 0 && ` · ${latest.failed} failed`}
          </span>
        </div>
        <div className="h-2 w-40 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full bg-blue-600 transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
        <button
          onClick={() => cancel.mutate()}
          className="flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-700 hover:bg-slate-100"
        >
          <StopCircle className="h-4 w-4" /> Cancel
        </button>
      </div>
    );
  }

  const label =
    latest && latest.status === "completed"
      ? `Last scan: ${latest.classified.toLocaleString()} classified`
      : latest
      ? `Last scan ${latest.status}`
      : "No scan yet";

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-slate-500">{label}</span>
      {failedCount > 0 && (
        <button
          disabled={retry.isPending}
          onClick={() => retry.mutate()}
          className="flex items-center gap-1.5 rounded-md border border-amber-300 bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-50"
          title="Re-classify photos and videos that failed"
        >
          <AlertTriangle className="h-4 w-4" />
          Retry {failedCount.toLocaleString()} failed
        </button>
      )}
      <button
        disabled={!authed || start.isPending}
        onClick={() => start.mutate()}
        className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
        title={authed ? "" : "Connect Google Drive first"}
      >
        {latest ? (
          <>
            <RefreshCw className="h-4 w-4" /> Rescan
          </>
        ) : (
          <>
            <Play className="h-4 w-4" /> Start scan
          </>
        )}
      </button>
    </div>
  );
}
