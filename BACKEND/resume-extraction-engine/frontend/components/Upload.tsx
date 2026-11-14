"use client";
import { useRef, useState } from "react";

const MAX = 10 * 1024 * 1024;
const OK = [".pdf", ".docx"];

export default function Upload({ onExtract, busy, progress, error }: {
  onExtract: (f: File) => void; busy: boolean; progress: number; error: string | null;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function pick(f?: File) {
    if (!f) return;
    const ext = f.name.slice(f.name.lastIndexOf(".")).toLowerCase();
    if (!OK.includes(ext)) return setErr("Only PDF and DOCX files are supported.");
    if (f.size > MAX) return setErr("File is larger than 10 MB.");
    if (f.size === 0) return setErr("File is empty.");
    setErr(null); setFile(f);
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-2xl font-semibold">Upload Your Resume</h1>
      <p className="mt-1 text-sm text-gray-600">Upload your existing resume to automatically extract your professional information.</p>
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
        className={`mt-6 rounded-xl border-2 border-dashed p-10 text-center ${drag ? "border-blue-500 bg-blue-50" : "border-gray-300"}`}>
        <p className="text-gray-700">Drag and drop your resume here</p>
        <button className="mt-3 rounded bg-gray-900 px-4 py-2 text-white" onClick={() => input.current?.click()} disabled={busy}>
          {file ? "Replace file" : "Browse Files"}
        </button>
        <input ref={input} type="file" hidden accept=".pdf,.docx" onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
        <p className="mt-3 text-xs text-gray-500">PDF or DOCX · max 10 MB · one resume at a time</p>
      </div>
      {file && (
        <div className="mt-4 flex items-center justify-between rounded border p-3 text-sm">
          <div><div className="font-medium">{file.name}</div>
            <div className="text-gray-500">{(file.size / 1024).toFixed(0)} KB · {file.name.split(".").pop()?.toUpperCase()}</div></div>
          <button className="text-red-600" onClick={() => setFile(null)} disabled={busy}>Remove</button>
        </div>
      )}
      {busy && <div className="mt-3 h-2 rounded bg-gray-200"><div className="h-2 rounded bg-blue-600" style={{ width: `${progress}%` }} /></div>}
      {(err || error) && <p className="mt-3 text-sm text-red-600" role="alert">{err ?? error}</p>}
      <button className="mt-5 w-full rounded bg-blue-600 py-2 font-medium text-white disabled:opacity-40" disabled={!file || busy} onClick={() => file && onExtract(file)}>
        {busy ? `Uploading… ${progress}%` : "Extract Resume"}
      </button>
      <p className="mt-4 text-xs text-gray-500">Your resume is processed securely. Uploaded documents are not publicly accessible.</p>
    </div>
  );
}
