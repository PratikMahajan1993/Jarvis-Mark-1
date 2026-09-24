"use client";

import { useState } from "react";
import GlareHover from "@/components/react-bits/GlareHover";
import GradientText from "@/components/react-bits/GradientText";
import SpotlightCard from "@/components/react-bits/SpotlightCard";

export type SuggestedTask = {
  id: string;
  kind: string;
  title: string;
  detail: string;
  actions: { id: string; label: string }[];
  status?: string;
  source_id?: string;
  meta?: Record<string, unknown>;
};

function plainDetail(raw: string): string {
  if (!raw) return "";
  let text = raw
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*$/gi, " ")
    .replace(/<script[\s\S]*$/gi, " ");
  text = text.replace(/<[^>]+>/g, " ");
  text = text
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'");
  const cssCut = text.search(/@media\b|behavior\s*:\s*url|v\\:\*|o\\:\*|w\\:\*/i);
  if (cssCut >= 0) text = text.slice(0, cssCut);
  return text.replace(/\s+/g, " ").trim();
}

function TaskCard({
  task,
  onAction,
  onDismiss,
}: {
  task: SuggestedTask;
  onAction: (task: SuggestedTask, actionId: string) => void;
  onDismiss: (taskId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const open = () => setExpanded(true);
  const close = () => setExpanded(false);

  return (
    <GlareHover
      className="rounded-lg"
      glareColor="#7dffe0"
      glareOpacity={0.22}
      glareSize={180}
      transitionDuration={520}
    >
      <SpotlightCard
        className="rounded-lg border border-[color:var(--border)] bg-black/50 shadow-[0_16px_32px_rgba(0,0,0,0.4)] backdrop-blur-md transition-[box-shadow] duration-300 hover:border-[color:var(--accent)]/35"
        bodyClassName="px-4 py-3"
      >
        <div
          className="group"
          onMouseEnter={open}
          onMouseLeave={close}
          onFocusCapture={open}
          onBlurCapture={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) close();
          }}
        >
          <div
            className={[
              "flex items-start justify-between gap-2 overflow-hidden transition-all duration-200",
              expanded ? "mb-2 max-h-8 opacity-100" : "mb-0 max-h-0 opacity-0",
            ].join(" ")}
          >
            <div className="font-mono text-[0.65rem] uppercase tracking-[0.12em] text-[color:var(--accent)]">
              {task.kind}
            </div>
            <button
              type="button"
              tabIndex={expanded ? 0 : -1}
              className="text-[0.7rem] text-white/35 hover:text-white/70"
              onClick={() => onDismiss(task.id)}
            >
              Dismiss
            </button>
          </div>

          <h3 className="font-display text-base leading-snug text-[color:var(--fg)] sm:text-lg">
            {task.title}
          </h3>
          <p className="mt-1.5 text-[0.8rem] leading-relaxed text-[color:var(--muted)] line-clamp-3">
            {plainDetail(task.detail)}
          </p>

          <div
            className={[
              "grid transition-[grid-template-rows,opacity,margin] duration-200 ease-out",
              expanded ? "mt-3 grid-rows-[1fr] opacity-100" : "mt-0 grid-rows-[0fr] opacity-0",
            ].join(" ")}
          >
            <div className="min-h-0 overflow-hidden">
              <div className="flex flex-col gap-2 pt-0.5">
                {(task.actions || []).map((action) => (
                  <button
                    key={action.id}
                    type="button"
                    tabIndex={expanded ? 0 : -1}
                    className="rounded-md border border-[color:var(--border)] px-3 py-2 text-left text-[0.8rem] text-[color:var(--fg)] transition hover:border-[color:var(--accent)] hover:bg-white/5"
                    onClick={() => onAction(task, action.id)}
                  >
                    {action.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </SpotlightCard>
    </GlareHover>
  );
}

export function SuggestedTasksPanel({
  tasks,
  onAction,
  onDismiss,
  variant = "suggested",
}: {
  tasks: SuggestedTask[];
  onAction: (task: SuggestedTask, actionId: string) => void;
  onDismiss: (taskId: string) => void;
  variant?: "suggested" | "findings";
}) {
  const heading = variant === "findings" ? "Findings" : "Suggested";

  return (
    <section
      className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden"
      aria-label={variant === "findings" ? "Agent findings" : "Suggested tasks"}
      data-tasks-panel
    >
      <div className="shrink-0 px-0.5">
        <GradientText
          className="font-mono text-[0.65rem] uppercase tracking-[0.16em]"
          animationSpeed={10}
        >
          {heading}
        </GradientText>
      </div>
      <div
        data-tasks-scroll
        className="min-h-0 flex-1 space-y-3 overflow-y-auto overflow-x-hidden pr-1 [scrollbar-width:thin] [scrollbar-color:rgba(125,255,224,0.25)_transparent]"
      >
        {tasks.length ? (
          tasks.map((task) => (
            <TaskCard key={task.id} task={task} onAction={onAction} onDismiss={onDismiss} />
          ))
        ) : (
          <p className="px-1 font-mono text-[10px] uppercase tracking-[0.14em] text-[color:var(--muted)]/55">
            Nothing queued
          </p>
        )}
      </div>
    </section>
  );
}
