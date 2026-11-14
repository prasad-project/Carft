"use client";
import { useEffect, useRef, useState } from "react";
import Processing from "@/components/Processing";
import Results from "@/components/Results";
import Upload from "@/components/Upload";
import { getResult, getStatus, startExtraction, upload } from "@/lib/api";
import type { ResumeResult, StatusPayload } from "@/types/resume";

type Step = "upload" | "processing" | "results";

export default function Home() {
  const [step, setStep] = useState<Step>("upload");
  const [pct, setPct] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [result, setResult] = useState<ResumeResult | null>(null);
  const ids = useRef<{ id: string; token: string } | null>(null);   // in memory only
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = () => { if (timer.current) clearInterval(timer.current); timer.current = null; };
  useEffect(() => stop, []);

  function poll() {
    stop();
    timer.current = setInterval(async () => {
      if (!ids.current) return;
      try {
        const s = await getStatus(ids.current.id, ids.current.token);
        setStatus(s);
        if (s.status === "completed") {
          stop();
          setResult(await getResult(ids.current.id, ids.current.token));
          setStep("results");
        } else if (s.status === "failed") stop();
      } catch (e) { stop(); setErr((e as Error).message); setStep("upload"); }
    }, 700);
  }

  async function begin(file: File) {
    setBusy(true); setErr(null); setPct(0);
    try {
      const up = await upload(file, setPct);
      ids.current = { id: up.resume_id, token: up.owner_token };
      setStatus(null); setStep("processing");
      setStatus(await startExtraction(up.resume_id, up.owner_token));
      poll();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  async function retry() {
    if (!ids.current) return;
    try { setStatus(await startExtraction(ids.current.id, ids.current.token)); poll(); } catch (e) { setErr((e as Error).message); }
  }
  function reset() { stop(); ids.current = null; setResult(null); setStatus(null); setStep("upload"); }

  return (
    <main className="min-h-screen p-6 sm:p-10">
      {step === "upload" && <Upload onExtract={begin} busy={busy} progress={pct} error={err} />}
      {step === "processing" && <Processing s={status} onRetry={retry} />}
      {step === "results" && result && ids.current && <Results initial={result} id={ids.current.id} token={ids.current.token} onReset={reset} />}
    </main>
  );
}
