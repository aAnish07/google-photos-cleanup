import { HardDrive, Image as ImageIcon, Trash2 } from "lucide-react";
import { useStats } from "../hooks/usePhotos";
import { formatBytes, KEEP_SIGNAL_COLORS, prettyLabel } from "../types";

function Card({
  icon,
  label,
  value,
  sub,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2">
      <div className="text-slate-400">{icon}</div>
      <div>
        <div className="text-xs text-slate-500">{label}</div>
        <div className="text-lg font-semibold leading-tight">{value}</div>
        {sub && <div className="text-xs text-slate-400">{sub}</div>}
      </div>
    </div>
  );
}

export default function StatsPanel() {
  const { data: stats } = useStats();
  if (!stats) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        <Card
          icon={<ImageIcon className="h-5 w-5" />}
          label="Photos"
          value={stats.total_photos.toLocaleString()}
        />
        <Card
          icon={<HardDrive className="h-5 w-5" />}
          label="Storage"
          value={formatBytes(stats.total_size_bytes)}
        />
        <Card
          icon={<Trash2 className="h-5 w-5" />}
          label="Recoverable"
          value={formatBytes(stats.estimated_recoverable_bytes)}
          sub="likely / definitely delete"
        />
      </div>

      <div className="rounded-lg border border-slate-200 bg-white p-3">
        <div className="mb-2 text-sm font-medium text-slate-700">
          By keep signal
        </div>
        <div className="space-y-1.5">
          {Object.entries(stats.by_keep_signal)
            .sort((a, b) => b[1].count - a[1].count)
            .map(([key, g]) => {
              const colors = KEEP_SIGNAL_COLORS[key];
              const pct =
                stats.total_photos > 0
                  ? (g.count / stats.total_photos) * 100
                  : 0;
              return (
                <div key={key}>
                  <div className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5">
                      <span
                        className={`h-2 w-2 rounded-full ${colors?.dot ?? "bg-slate-400"}`}
                      />
                      {colors?.label ?? prettyLabel(key)}
                    </span>
                    <span className="text-slate-500">
                      {g.count.toLocaleString()} · {formatBytes(g.size_bytes)}
                    </span>
                  </div>
                  <div className="mt-0.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className={`h-full ${colors?.dot ?? "bg-slate-400"}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          {Object.keys(stats.by_keep_signal).length === 0 && (
            <div className="text-xs text-slate-400">No classified photos yet.</div>
          )}
        </div>
      </div>
    </div>
  );
}
