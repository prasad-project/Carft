"use client";
import { useEffect, useMemo, useState } from "react";
import { deleteResume, downloadUrl, getText, saveResult } from "@/lib/api";
import type { Entry, ResumeResult } from "@/types/resume";

const HIDE = new Set(["source_page", "source_text", "confidence", "status"]);
const copy = (t: string) => navigator.clipboard?.writeText(t);

function Section({ title, count, children, open = true }: { title: string; count?: number; children: React.ReactNode; open?: boolean }) {
  const [o, setO] = useState(open);
  return (
    <section className="rounded-lg border">
      <button className="flex w-full items-center justify-between px-4 py-3 text-left font-medium" onClick={() => setO(!o)}>
        <span>{title}{count !== undefined && <span className="ml-2 text-xs text-gray-500">({count})</span>}</span><span>{o ? "−" : "+"}</span>
      </button>
      {o && <div className="space-y-3 border-t p-4">{children}</div>}
    </section>
  );
}

function Row({ k, v }: { k: string; v: unknown }) {
  if (v === null || v === undefined || v === "" || (Array.isArray(v) && !v.length) || v === false) return null;
  const text = Array.isArray(v) ? v.join(", ") : String(v);
  return (
    <div className="flex gap-2 text-sm">
      <div className="w-36 shrink-0 text-gray-500">{k.replace(/_/g, " ")}</div>
      <div className="flex-1 break-words">{text}</div>
      <button className="text-xs text-blue-600" onClick={() => copy(text)}>copy</button>
    </div>
  );
}

function EntryCard({ e }: { e: Entry }) {
  const review = e.status === "needs_review";
  return (
    <div className={`rounded border p-3 ${review ? "border-amber-400 bg-amber-50" : ""}`} title={e.source_text ?? undefined}>
      {review && <div className="mb-1 text-xs font-medium text-amber-700">Needs review · confidence {e.confidence} · page {e.source_page}</div>}
      {Object.entries(e).filter(([k]) => !HIDE.has(k)).map(([k, v]) => <Row key={k} k={k} v={v} />)}
    </div>
  );
}

export default function Results({ initial, id, token, onReset }: { initial: ResumeResult; id: string; token: string; onReset: () => void }) {
  const [r, setR] = useState(initial);
  const [q, setQ] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [text, setText] = useState<string>("");
  const m = r.extraction_metadata;
  useEffect(() => { getText(id, token).then((t) => setText(t.pages.map((p) => `--- page ${p.page} (${p.method}) ---\n${p.text}`).join("\n\n"))).catch(() => {}); }, [id, token]);

  const match = (x: unknown) => !q || JSON.stringify(x).toLowerCase().includes(q.toLowerCase());
  const lists: [string, Entry[]][] = useMemo(() => [
    ["Education", r.education], ["Work Experience", r.experience], ["Projects", r.projects],
    ["Certifications", r.certifications], ["Achievements", r.achievements], ["Awards", r.awards],
    ["Publications", r.publications], ["Languages", r.languages], ["Volunteer Experience", r.volunteer_experience], ["Training", r.training],
  ], [r]);

  function setPersonal(k: string, v: string) {
    setR({ ...r, personal_information: { ...r.personal_information, [k]: v || null } });
  }
  async function save() {
    try { setR(await saveResult(id, token, r)); setMsg("Saved."); } catch (e) { setMsg((e as Error).message); }
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[1fr_340px]">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-2xl font-semibold">Your Resume Information</h1>
          <div className="flex flex-wrap gap-2 text-sm">
            <button className="rounded border px-3 py-1" onClick={() => copy(JSON.stringify(r, null, 2))}>Copy JSON</button>
            <a className="rounded border px-3 py-1" href={downloadUrl(id, token, "json")}>Download JSON</a>
            <a className="rounded border px-3 py-1" href={downloadUrl(id, token, "text")}>Download text</a>
            <button className="rounded border px-3 py-1" onClick={async () => { await deleteResume(id, token); onReset(); }}>Delete &amp; start over</button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          {[["Pages", r.document.total_pages], ["Method", r.document.extraction_method], ["OCR used", r.document.ocr_used ? `yes (p. ${m.ocr_pages.join(",")})` : "no"], ["Fields found", m.extracted_field_count]].map(([k, v]) => (
            <div key={String(k)} className="rounded border p-2"><div className="text-xs text-gray-500">{k}</div><div className="font-medium">{String(v)}</div></div>
          ))}
        </div>
        {m.warnings.map((w) => <p key={w} className="rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800">⚠ {w}</p>)}
        {m.missing_fields.length > 0 && <p className="text-sm text-gray-600">Not found: {m.missing_fields.join(", ")}</p>}
        <input className="w-full rounded border px-3 py-2 text-sm" placeholder="Search extracted information…" value={q} onChange={(e) => setQ(e.target.value)} />

        <Section title="Personal Information">
          {Object.entries(r.personal_information).filter(([k, v]) => match([k, v])).map(([k, v]) => {
            const t = m.field_traces[`personal_information.${k}`];
            return (
              <label key={k} className="flex items-center gap-2 text-sm" title={t?.source_text ?? undefined}>
                <span className="w-36 shrink-0 text-gray-500">{k.replace(/_/g, " ")}</span>
                <input className={`flex-1 rounded border px-2 py-1 ${t?.status === "needs_review" ? "border-amber-400 bg-amber-50" : ""}`} value={v ?? ""} onChange={(e) => setPersonal(k, e.target.value)} />
                {t && <span className="w-16 text-xs text-gray-500">{Math.round(t.confidence * 100)}%</span>}
                <button className="text-xs text-blue-600" onClick={() => copy(v ?? "")}>copy</button>
              </label>
            );
          })}
          <div className="flex items-center gap-3"><button className="rounded bg-blue-600 px-3 py-1 text-sm text-white" onClick={save}>Save corrections</button>{msg && <span className="text-sm text-gray-600">{msg}</span>}</div>
        </Section>
        <Section title="Social Profiles">{Object.entries(r.social_profiles).filter(([k, v]) => match([k, v])).map(([k, v]) => <Row key={k} k={k} v={v} />)}</Section>
        {lists.map(([title, items]) => {
          const shown = items.filter(match);
          return items.length ? <Section key={title} title={title} count={shown.length}>{shown.map((e, i) => <EntryCard key={i} e={e} />)}</Section> : null;
        })}
        <Section title="Skills">{Object.entries(r.skills).filter(([, v]) => v.length).map(([k, v]) => <Row key={k} k={k === "inferred_from_context" ? "unconfirmed (from context)" : k} v={v.filter((x) => match(x))} />)}</Section>
        {(r.interests.length > 0 || r.additional_information.length > 0) && (
          <Section title="Additional Information">
            <Row k="interests" v={r.interests} />
            {r.additional_information.map((a, i) => <Row key={i} k={a.section} v={a.text} />)}
          </Section>
        )}
        {r.unclassified_text.length > 0 && (
          <Section title="Additional Extracted Text" count={r.unclassified_text.length} open={false}>
            {r.unclassified_text.map((u, i) => <p key={i} className="text-sm text-gray-700">{u.text} <span className="text-xs text-gray-400">(p. {u.source_page})</span></p>)}
          </Section>
        )}
      </div>
      <aside className="lg:sticky lg:top-4 lg:self-start">
        <h2 className="mb-2 font-medium">Extracted text</h2>
        <pre className="max-h-[80vh] overflow-auto whitespace-pre-wrap rounded border bg-gray-50 p-3 text-xs">{text || "Loading…"}</pre>
      </aside>
    </div>
  );
}
