import type { ResumeResult, StatusPayload, UploadResponse } from "@/types/resume";

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const base = `${API}/api/v1/resumes`;

async function j<T>(p: Promise<Response>): Promise<T> {
  const r = await p.catch(() => { throw new Error("Cannot reach the server"); });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body?.detail?.message ?? `Request failed (${r.status})`);
  }
  return r.json();
}

/** XHR (not fetch) so we get real upload progress. */
export function upload(file: File, onProgress: (pct: number) => void): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${base}/upload`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText);
        xhr.status === 201 ? resolve(body) : reject(new Error(body?.detail?.message ?? "Upload failed"));
      } catch { reject(new Error("Upload failed")); }
    };
    xhr.onerror = () => reject(new Error("Cannot reach the server"));
    const fd = new FormData();
    fd.append("file", file);
    xhr.send(fd);
  });
}

const h = (token: string) => ({ "X-Owner-Token": token });
export const startExtraction = (id: string, token: string) =>
  j<StatusPayload>(fetch(`${base}/extract`, { method: "POST", headers: { ...h(token), "Content-Type": "application/json" }, body: JSON.stringify({ resume_id: id }) }));
export const getStatus = (id: string, token: string) => j<StatusPayload>(fetch(`${base}/${id}/status`, { headers: h(token) }));
export const getResult = (id: string, token: string) => j<ResumeResult>(fetch(`${base}/${id}/result`, { headers: h(token) }));
export const getText = (id: string, token: string) => j<{ pages: { page: number; method: string; text: string }[] }>(fetch(`${base}/${id}/text`, { headers: h(token) }));
export const saveResult = (id: string, token: string, data: ResumeResult) =>
  j<ResumeResult>(fetch(`${base}/${id}/result`, { method: "PUT", headers: { ...h(token), "Content-Type": "application/json" }, body: JSON.stringify(data) }));
export const deleteResume = (id: string, token: string) => fetch(`${base}/${id}`, { method: "DELETE", headers: h(token) });
export const downloadUrl = (id: string, token: string, kind: "json" | "text") =>
  `${base}/${id}/download-${kind}?token=${encodeURIComponent(token)}`;
