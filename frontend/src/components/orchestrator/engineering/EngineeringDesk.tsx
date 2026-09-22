"use client";

import { useMemo } from "react";
import type { MailAttachment, Scene } from "@/lib/types";
import {
  conversationToAttachment,
  isSavedLocal,
  sceneAttachments,
} from "@/lib/viewerMatch";
import { DrawingViewer } from "@/components/DrawingViewer";
import GradientText from "@/components/react-bits/GradientText";
import SpotlightCard from "@/components/react-bits/SpotlightCard";
import { QuoteStack } from "./QuoteStack";
import { CustomerVisionConsent } from "./CustomerVisionConsent";
import { VisionBenchQueue } from "./VisionBenchQueue";
import { FactConfirmChips } from "./FactConfirmChips";
import { VarianceCard } from "./VarianceCard";
import { ToolChangeField } from "./ToolChangeField";

const BENCH_BG = "#060a0e";

function isViewableDrawing(att: MailAttachment): boolean {
  if (!isSavedLocal(att)) return false;
  const name = (att.local_name || att.filename || "").toLowerCase();
  const mime = (att.mime || "").toLowerCase();
  if (name.endsWith(".pdf") || mime.includes("pdf")) return true;
  if (/\.(png|jpe?g|gif|webp|bmp|tiff?|svg)$/i.test(name)) return true;
  if (mime.startsWith("image/")) return true;
  return Boolean(att.readable);
}

function pickDrawingAttachment(
  scene: Scene,
  focus?: Record<string, unknown>,
): MailAttachment | null {
  const fromFocus = conversationToAttachment(focus);
  if (fromFocus && isViewableDrawing(fromFocus)) return fromFocus;

  for (const att of sceneAttachments(scene)) {
    if (isViewableDrawing(att)) return att;
  }
  return null;
}

function CompactVoice({ text, dimmed }: { text: string; dimmed?: boolean }) {
  return (
    <div
      className={[
        "shrink-0 rounded-xl border border-[color:var(--border)] bg-black/40 px-4 py-3 backdrop-blur-md transition-opacity duration-[600ms]",
        dimmed ? "opacity-35" : "",
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <p className="mb-1 font-mono text-[10px] uppercase tracking-[0.2em] text-[color:var(--accent)]/65">
        Status
      </p>
      <p className="font-display text-[1.05rem] leading-snug text-[color:var(--fg)] whitespace-pre-wrap break-words">
        {text}
      </p>
    </div>
  );
}

export function EngineeringDesk({
  scene,
  focusTitle,
  focus,
  voice,
  voiceVisible,
  dimmed,
  entityType = "",
  entityId = "",
}: {
  scene: Scene;
  focusTitle: string;
  focus?: Record<string, unknown>;
  voice: string;
  voiceVisible?: boolean;
  dimmed?: boolean;
  entityType?: string;
  entityId?: string;
}) {
  const drawing = useMemo(() => pickDrawingAttachment(scene, focus), [scene, focus]);
  const jobTitle = (scene.title || "").trim() || focusTitle;

  return (
    <>
      <div
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background: `radial-gradient(ellipse 120% 80% at 30% 40%, rgba(125, 255, 224, 0.04), transparent 55%), ${BENCH_BG}`,
        }}
      />
      <div
        className="pointer-events-none absolute inset-0 z-0 opacity-[0.35]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(125,255,224,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(125,255,224,0.04) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      <div className="pointer-events-auto absolute inset-x-0 top-[4.25rem] bottom-[5.25rem] z-[1] flex flex-col px-5 md:px-8">
        <header className="mb-3 shrink-0 pl-10">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[color:var(--muted)]/60">
            Engineering bench
          </p>
          <h1 className="font-display text-2xl tracking-wide text-[color:var(--fg)] md:text-3xl">
            {jobTitle}
          </h1>
          {scene.subtitle ? (
            <p className="mt-0.5 text-xs text-[color:var(--muted)]">{scene.subtitle}</p>
          ) : null}
        </header>

        <div className="flex min-h-0 flex-1 gap-4">
          <SpotlightCard
            className="flex w-[55%] min-w-0 flex-col rounded-2xl border border-[color:var(--border)] bg-black/40 backdrop-blur-md"
            bodyClassName="relative min-h-0 flex-1 overflow-hidden p-0"
          >
            <div className="shrink-0 border-b border-[color:var(--border)] px-4 py-2">
              <GradientText
                className="font-mono text-[10px] uppercase tracking-[0.22em]"
                animationSpeed={9}
              >
                Drawing
              </GradientText>
            </div>
            <div className="relative min-h-0 flex-1">
              {drawing ? (
                <DrawingViewer
                  embedded
                  attachment={drawing}
                  onClose={() => undefined}
                  onWhisper={() => undefined}
                />
              ) : (
                <div className="flex h-full min-h-[280px] flex-col items-center justify-center gap-2 px-6 text-center">
                  <p className="font-display text-lg text-[color:var(--fg)]/75">
                    No drawing in this job yet.
                  </p>
                  <p className="max-w-xs font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--muted)]/65">
                    Attachments appear here when saved locally.
                  </p>
                </div>
              )}
            </div>
          </SpotlightCard>

          <div className="flex w-[40%] min-w-0 flex-col gap-3 min-h-0">
            {voiceVisible !== false ? (
              <CompactVoice text={voice} dimmed={dimmed} />
            ) : null}
            <CustomerVisionConsent />
            <VisionBenchQueue />
            <FactConfirmChips entityType={entityType} entityId={entityId} />
            <VarianceCard />
            <ToolChangeField />
            <QuoteStack scene={scene} />
          </div>
        </div>
      </div>
    </>
  );
}
