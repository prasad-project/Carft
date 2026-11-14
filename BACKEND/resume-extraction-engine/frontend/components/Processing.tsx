"use client";
import type { StatusPayload } from "@/types/resume";

/** Renders ONLY what the backend reports: stage states come from GET /status. */
export default function Processing({ s, onRetry }: { s: StatusPayload | null; onRetry: () => void }) {
  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-2xl font-semibold">Extracting Your Resume Information</h1>
      <div className="mt-4 h-2 rounded bg-gray-200"><div className="h-2 rounded bg-blue-600 transition-all" style={{ width: `${Math.round((s?.progress ?? 0) * 100)}%` }} /></div>
      <p className="mt-2 text-sm text-gray-600">{s?.current_stage_name ?? "Starting…"}{s?.detail ? ` — ${s.detail}` : ""}</p>
      <ol className="mt-4 space-y-1 text-sm">
        {s?.stages.map((st) => (
          <li key={st.index} className={st.state === "done" ? "text-green-700" : st.state === "running" ? "font-medium" : st.state === "failed" ? "text-red-600" : "text-gray-400"}>
            {st.state === "done" ? "✓" : st.state === "running" ? "…" : st.state === "failed" ? "✗" : "○"} {st.index}. {st.name}
          </li>
        ))}
      </ol>
      {s?.status === "failed" && (
        <div className="mt-4 rounded border border-red-300 bg-red-50 p-3 text-sm">
          <p className="text-red-700">{s.error?.message ?? "Extraction failed."}</p>
          <button className="mt-2 rounded bg-red-600 px-3 py-1 text-white" onClick={onRetry}>Retry</button>
        </div>
      )}
    </div>
  );
}
