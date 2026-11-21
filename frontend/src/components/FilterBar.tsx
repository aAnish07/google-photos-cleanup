import { RotateCcw } from "lucide-react";
import { useStats } from "../hooks/usePhotos";
import {
  EMPTY_FILTERS,
  Filters,
  KEEP_SIGNALS,
  KEEP_SIGNAL_COLORS,
  PHOTO_TYPES,
  QUALITY_SIGNALS,
  prettyLabel,
} from "../types";

interface Props {
  filters: Filters;
  onChange: (f: Filters) => void;
}

function toggle(list: string[], value: string): string[] {
  return list.includes(value)
    ? list.filter((v) => v !== value)
    : [...list, value];
}

export default function FilterBar({ filters, onChange }: Props) {
  const { data: stats } = useStats();

  const countFor = (group: "by_type" | "by_quality", key: string) =>
    stats?.[group]?.[key]?.count ?? 0;

  const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
    <div className="border-b border-slate-200 py-3">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {title}
      </div>
      {children}
    </div>
  );

  const Checkbox = ({
    checked,
    onToggle,
    label,
    count,
    dot,
  }: {
    checked: boolean;
    onToggle: () => void;
    label: string;
    count?: number;
    dot?: string;
  }) => (
    <label className="flex cursor-pointer items-center justify-between py-0.5 text-sm hover:text-slate-900">
      <span className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          className="h-3.5 w-3.5 rounded border-slate-300"
        />
        {dot && <span className={`h-2 w-2 rounded-full ${dot}`} />}
        <span>{label}</span>
      </span>
      {count !== undefined && (
        <span className="text-xs text-slate-400">{count}</span>
      )}
    </label>
  );

  return (
    <div className="flex h-full flex-col overflow-y-auto px-4 pb-6">
      <div className="flex items-center justify-between py-3">
        <span className="text-sm font-semibold text-slate-700">Filters</span>
        <button
          onClick={() => onChange(EMPTY_FILTERS)}
          className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800"
        >
          <RotateCcw className="h-3 w-3" /> Reset
        </button>
      </div>

      <Section title="Keep signal">
        {KEEP_SIGNALS.map((k) => (
          <Checkbox
            key={k}
            checked={filters.keep_signal.includes(k)}
            onToggle={() =>
              onChange({ ...filters, keep_signal: toggle(filters.keep_signal, k) })
            }
            label={KEEP_SIGNAL_COLORS[k].label}
            dot={KEEP_SIGNAL_COLORS[k].dot}
            count={stats?.by_keep_signal?.[k]?.count}
          />
        ))}
      </Section>

      <Section title="Photo type">
        {PHOTO_TYPES.map((t) => (
          <Checkbox
            key={t}
            checked={filters.photo_type.includes(t)}
            onToggle={() =>
              onChange({ ...filters, photo_type: toggle(filters.photo_type, t) })
            }
            label={prettyLabel(t)}
            count={countFor("by_type", t)}
          />
        ))}
      </Section>

      <Section title="Quality">
        {QUALITY_SIGNALS.map((q) => (
          <Checkbox
            key={q}
            checked={filters.quality_signal.includes(q)}
            onToggle={() =>
              onChange({
                ...filters,
                quality_signal: toggle(filters.quality_signal, q),
              })
            }
            label={prettyLabel(q)}
            count={countFor("by_quality", q)}
          />
        ))}
      </Section>

      <Section title="Contains text">
        <select
          value={filters.has_text}
          onChange={(e) =>
            onChange({ ...filters, has_text: e.target.value as Filters["has_text"] })
          }
          className="w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
        >
          <option value="">Any</option>
          <option value="yes">Has text</option>
          <option value="no">No text</option>
        </select>
      </Section>

      <Section title="Date range">
        <div className="flex flex-col gap-1.5">
          <input
            type="date"
            value={filters.date_from.slice(0, 10)}
            onChange={(e) =>
              onChange({
                ...filters,
                date_from: e.target.value ? `${e.target.value}T00:00:00Z` : "",
              })
            }
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
          <input
            type="date"
            value={filters.date_to.slice(0, 10)}
            onChange={(e) =>
              onChange({
                ...filters,
                date_to: e.target.value ? `${e.target.value}T23:59:59Z` : "",
              })
            }
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
        </div>
      </Section>

      <Section title="Minimum size">
        <div className="flex gap-1.5">
          {[
            { label: "Any", v: null },
            { label: ">1MB", v: 1_000_000 },
            { label: ">5MB", v: 5_000_000 },
          ].map((opt) => (
            <button
              key={opt.label}
              onClick={() => onChange({ ...filters, min_size: opt.v })}
              className={`flex-1 rounded-md border px-2 py-1 text-xs ${
                filters.min_size === opt.v
                  ? "border-blue-500 bg-blue-50 text-blue-700"
                  : "border-slate-300 text-slate-600 hover:bg-slate-50"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </Section>

      <Section title={`Min confidence: ${filters.min_confidence.toFixed(2)}`}>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={filters.min_confidence}
          onChange={(e) =>
            onChange({ ...filters, min_confidence: parseFloat(e.target.value) })
          }
          className="w-full"
        />
      </Section>

      <Section title="Sort">
        <div className="flex gap-1.5">
          <select
            value={filters.sort}
            onChange={(e) =>
              onChange({ ...filters, sort: e.target.value as Filters["sort"] })
            }
            className="flex-1 rounded-md border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="created_time">Date</option>
            <option value="size_bytes">Size</option>
            <option value="photo_type_confidence">Confidence</option>
          </select>
          <select
            value={filters.order}
            onChange={(e) =>
              onChange({ ...filters, order: e.target.value as Filters["order"] })
            }
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          >
            <option value="desc">↓</option>
            <option value="asc">↑</option>
          </select>
        </div>
      </Section>
    </div>
  );
}
