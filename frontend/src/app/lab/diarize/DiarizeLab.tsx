"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ASR_MODEL,
  DIARIZE_MAX_SECONDS,
  EMBED_MODEL,
  clipDuration,
  createDiarizeClient,
  decodeToMono16k,
  encodeWav,
  startMic,
  type DiarizeClient,
  type DiarizeProgress,
  type DiarizeResult,
} from "@/lib/diarize";

const COLORS = ["#3ee0d4", "#f5c16c", "#7aa7ff", "#f08bd2", "#9ae6b4", "#ffb4a2"];

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

export default function DiarizeLab() {
  const clientRef = useRef<DiarizeClient | null>(null);
  const micRef = useRef<Awaited<ReturnType<typeof startMic>> | null>(null);
  const timerRef = useRef<number>(0);

  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [pcm, setPcm] = useState<Float32Array | null>(null);
  const [wavUrl, setWavUrl] = useState<string | null>(null);
  const [transcribe, setTranscribe] = useState(true);
  const [threshold, setThreshold] = useState(0.72);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<DiarizeProgress | null>(null);
  const [result, setResult] = useState<DiarizeResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    return () => {
      clientRef.current?.dispose();
      clientRef.current = null;
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
  }, []);

  useEffect(() => {
    return () => {
      if (wavUrl) URL.revokeObjectURL(wavUrl);
    };
  }, [wavUrl]);

  const setAudio = (next: Float32Array) => {
    const clipped = clipDuration(next);
    setPcm(clipped);
    setResult(null);
    setError("");
    setWavUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(encodeWav(clipped));
    });
  };

  const startRecording = async () => {
    setError("");
    setResult(null);
    try {
      micRef.current = await startMic();
      setRecording(true);
      setElapsed(0);
      timerRef.current = window.setInterval(() => {
        setElapsed((value) => {
          if (value + 1 >= DIARIZE_MAX_SECONDS) {
            void stopRecording();
            return DIARIZE_MAX_SECONDS;
          }
          return value + 1;
        });
      }, 1000);
    } catch {
      setError("Chrome did not get the microphone. Allow the mic for this page, then try again.");
    }
  };

  const stopRecording = async () => {
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = 0;
    const session = micRef.current;
    micRef.current = null;
    setRecording(false);
    if (!session) return;
    try {
      const captured = await session.stop();
      setAudio(captured.pcm);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not finish the recording.");
    }
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    setError("");
    try {
      setAudio(await decodeToMono16k(file));
    } catch {
      setError("That file could not be decoded. Try a WAV, MP3, or WebM clip.");
    }
  };

  const run = async () => {
    if (!pcm) return;
    if (!clientRef.current) clientRef.current = createDiarizeClient();
    setBusy(true);
    setError("");
    setProgress({ label: "Starting", progress: 0 });
    try {
      const next = await clientRef.current.diarize(
        pcm,
        { transcribe, threshold },
        (item) => setProgress(item),
      );
      setResult(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Diarization failed.");
    } finally {
      setBusy(false);
    }
  };

  const duration = pcm ? pcm.length / 16000 : 0;
  const speakers = useMemo(() => result?.speakers || [], [result]);

  return (
    <main className="hud-bg min-h-screen px-6 py-8 text-white/80">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
        <header>
          <p className="font-display text-xs tracking-[0.28em] text-cyan/70">LAB · NOT WIRED TO HUD</p>
          <h1 className="mt-2 font-display text-4xl font-semibold text-white">Offline diarize</h1>
          <p className="mt-2 max-w-2xl text-sm text-white/55">
            Records in the browser, then labels speakers with Transformers.js. Models download once from Hugging Face
            and stay in this browser&apos;s cache. The home HUD never loads this code.
          </p>
        </header>

        <section className="glass rounded-2xl p-5">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void (recording ? stopRecording() : startRecording())}
              className="rounded-full bg-cyan/15 px-4 py-2 text-sm text-cyan hover:bg-cyan/25"
            >
              {recording ? `Stop · ${formatTime(elapsed)}` : "Record"}
            </button>
            <label className="cursor-pointer rounded-full border border-white/10 px-4 py-2 text-sm text-white/70 hover:border-cyan/40">
              Upload audio
              <input
                type="file"
                accept="audio/*"
                className="hidden"
                onChange={(event) => void onFile(event.target.files?.[0])}
              />
            </label>
            <label className="flex items-center gap-2 text-sm text-white/60">
              <input
                type="checkbox"
                checked={transcribe}
                onChange={(event) => setTranscribe(event.target.checked)}
              />
              Also transcribe
            </label>
          </div>

          <label className="mt-4 flex items-center gap-3 text-sm text-white/55">
            Match tightness
            <input
              type="range"
              min={0.55}
              max={0.9}
              step={0.01}
              value={threshold}
              onChange={(event) => setThreshold(Number(event.target.value))}
            />
            <span className="text-white/80">{threshold.toFixed(2)}</span>
          </label>

          {pcm ? (
            <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
              <span className="text-white/70">{formatTime(duration)} captured</span>
              {wavUrl ? <audio controls src={wavUrl} className="h-9 max-w-full" /> : null}
              <button
                type="button"
                className="text-cyan/80 hover:text-cyan"
                onClick={() => wavUrl && download(encodeWav(pcm), "jarvis-diarize.wav")}
              >
                Download WAV
              </button>
            </div>
          ) : (
            <p className="mt-4 text-sm text-white/40">Record two people talking, or drop in a meeting clip. Max {DIARIZE_MAX_SECONDS / 60} minutes.</p>
          )}
        </section>

        <section className="glass rounded-2xl p-5">
          <button
            type="button"
            disabled={!pcm || busy}
            onClick={() => void run()}
            className="rounded-full bg-amber/20 px-4 py-2 text-sm text-amber disabled:opacity-40"
          >
            {busy ? "Working…" : "Diarize locally"}
          </button>
          {progress && busy ? (
            <p className="mt-3 text-sm text-white/55">
              {progress.label} · {progress.progress}%
            </p>
          ) : null}
          <p className="mt-3 text-xs text-white/35">
            Speakers: {EMBED_MODEL} (q8). Transcript: {ASR_MODEL}. First run needs the network; later runs are offline.
          </p>
          {error ? <p className="mt-3 text-sm text-amber">{error}</p> : null}
        </section>

        {result ? (
          <section className="glass rounded-2xl p-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-display text-xl text-white">
                {result.speakers.length ? `${result.speakers.length} speakers` : "No speech found"}
              </h2>
              <button
                type="button"
                className="text-sm text-cyan/80 hover:text-cyan"
                onClick={() =>
                  download(new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }), "jarvis-diarize.json")
                }
              >
                Download JSON
              </button>
            </div>
            {result.duration > 0 ? (
              <div className="mt-4 flex h-6 overflow-hidden rounded-full bg-white/5">
                {result.turns.map((turn, index) => {
                  const speakerIndex = Math.max(0, speakers.indexOf(turn.speaker));
                  const width = ((turn.end - turn.start) / result.duration) * 100;
                  return (
                    <div
                      key={`${turn.speaker}-${index}`}
                      title={`${turn.speaker} ${formatTime(turn.start)}–${formatTime(turn.end)}`}
                      style={{ width: `${width}%`, background: COLORS[speakerIndex % COLORS.length] }}
                      className="h-full opacity-80"
                    />
                  );
                })}
              </div>
            ) : null}
            <ul className="mt-4 space-y-3">
              {result.turns.map((turn, index) => {
                const speakerIndex = Math.max(0, speakers.indexOf(turn.speaker));
                return (
                  <li key={`${turn.start}-${index}`} className="flex gap-3 text-sm">
                    <span
                      className="mt-1 h-3 w-3 shrink-0 rounded-full"
                      style={{ background: COLORS[speakerIndex % COLORS.length] }}
                    />
                    <div>
                      <p className="text-white/80">
                        {turn.speaker} · {formatTime(turn.start)}–{formatTime(turn.end)}
                      </p>
                      {turn.text ? <p className="text-white/55">{turn.text}</p> : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        ) : null}
      </div>
    </main>
  );
}
