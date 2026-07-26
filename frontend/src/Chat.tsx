import { useEffect, useRef, useState } from "react";

import { streamAgentMessage } from "./lib/agentStream";
import { Markdown } from "./lib/markdown";
import type { Meta } from "./lib/meta";
import { useReportSpecStore } from "./store/reportSpecStore";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  chips: string[];
}

/**
 * The Assistant chat panel (issue 15; docked as `AssistantPane` in issue
 * 02; markdown + visual pass in issue 06). Renders the presenter's small,
 * fixed vocabulary — a thinking row with an elapsed counter, chips as
 * badges on the Assistant's message, and streamed prose rendered as
 * markdown (architecture.md §6, §7). Never touches a tool name, a raw
 * argument or reasoning text outside the dev-only disclosure below — those
 * never arrive here in the first place, since `app/agent/presenter.py` is
 * the chokepoint that keeps them off the wire; this component only
 * *formats* what already arrives (`lib/markdown.tsx`'s docstring covers the
 * markdown-specific half of that guarantee).
 *
 * Reads and writes the single Report Spec store (`store/reportSpecStore.ts`)
 * directly rather than taking a spec via props: `buildSpec()` is the exact
 * spec the on-screen builder currently shows, sent as the starting point for
 * the Assistant's next turn (architecture.md §6: "a POST carrying state");
 * `applySpec` is called on every `spec` event, so the controls visibly move
 * one field at a time as the Assistant works (user story 38, ADR-0002) —
 * through the SAME store `BuilderPane`'s controls edit.
 */
export function Chat({ meta }: { meta: Meta | null }) {
  const buildSpec = useReportSpecStore((state) => state.buildSpec);
  const applySpec = useReportSpecStore((state) => state.applySpec);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [status, setStatus] = useState<string | null>(null);
  /** Raw reasoning text, development-only (architecture.md §6 "Dev-mode
   * exception"). Gated on `meta.dev_fake_llm` — the same runtime signal
   * `Header.tsx`'s DEV_FAKE_LLM banner already reads from `/api/v1/meta` —
   * rather than any build-time value, per the `VITE_*` hard rule. The
   * backend only ever streams the underlying `thinking_text` event when
   * `settings.is_development`, so this is a belt-and-suspenders display
   * gate on top of an event that already cannot arrive in production. */
  const [reasoning, setReasoning] = useState("");
  const devMode = Boolean(meta?.dev_fake_llm);

  /**
   * The polite, one-shot completion announcement (issue 08: frontend-rework
   * accessibility polish) — "a screen reader user learns the Assistant
   * answered without having the whole growing message re-read on every
   * token." This is deliberately NOT derived from the growing
   * `messages[...].text` itself: it is set exactly once, inside `onDone`
   * (and once for a failed turn, inside `onError`), so it can only ever
   * fire once per turn no matter how many `onToken` events land in
   * between. `onToken` must never write to this state — that would
   * reintroduce the exact per-token re-announcement this exists to avoid.
   * Paired with `role="log"`'s `aria-relevant="additions"` below (which
   * stops the log region itself from treating a text mutation inside an
   * already-added bubble as a reportable change) — together, the growing
   * bubble is silent while it grows and this region speaks once when it's
   * done.
   */
  const [announcement, setAnnouncement] = useState("");

  const timerRef = useRef<number | null>(null);
  const thinkingStartRef = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    },
    [],
  );

  function startThinkingTimer() {
    thinkingStartRef.current = Date.now();
    setElapsedMs(0);
    timerRef.current = window.setInterval(() => {
      if (thinkingStartRef.current !== null) {
        setElapsedMs(Date.now() - thinkingStartRef.current);
      }
    }, 100);
  }

  function stopThinkingTimer() {
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    thinkingStartRef.current = null;
  }

  async function send() {
    const text = input.trim();
    if (!text || busy) return;

    setInput("");
    setBusy(true);
    setStatus(null);
    setMessages((prev) => [
      ...prev,
      { role: "user", text, chips: [] },
      { role: "assistant", text: "", chips: [] },
    ]);

    function updateLastAssistantMessage(update: (message: ChatMessage) => ChatMessage) {
      setMessages((prev) => {
        const next = [...prev];
        const lastIndex = next.length - 1;
        next[lastIndex] = update(next[lastIndex]);
        return next;
      });
    }

    try {
      await streamAgentMessage(text, buildSpec(), {
        onThinking: (event) => {
          if (event.state === "start") {
            setThinking(true);
            startThinkingTimer();
          } else {
            setThinking(false);
            stopThinkingTimer();
          }
        },
        onStatus: (event) => setStatus(event.text),
        onChips: (event) => {
          updateLastAssistantMessage((message) => ({
            ...message,
            chips: [...message.chips, ...event.chips],
          }));
        },
        onSpec: (event) => applySpec(event.spec),
        onToken: (event) => {
          updateLastAssistantMessage((message) => ({
            ...message,
            text: message.text + event.text,
          }));
        },
        onDone: () => {
          setStatus(null);
          setBusy(false);
          setAnnouncement("Assistant replied.");
        },
        onError: (event) => {
          setStatus(null);
          setThinking(false);
          stopThinkingTimer();
          setBusy(false);
          updateLastAssistantMessage((message) => ({
            ...message,
            text: message.text || event.text,
          }));
          setAnnouncement("Assistant could not complete the reply.");
        },
        onThinkingText: (event) => {
          setReasoning((prev) => prev + event.text);
        },
      });
    } finally {
      setBusy(false);
      setThinking(false);
      stopThinkingTimer();
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* `role="log"` implies `aria-live="polite"` with a default
          `aria-relevant` of "additions text" — the "text" half is exactly
          the naive-live-region bug (re-announcing the whole growing
          message on every token, since each `onToken` mutates a text node
          already inside this region). `aria-relevant="additions"` narrows
          it to whole new messages only; the one-shot region below (outside
          this log) is what announces the turn finishing. */}
      <div
        role="log"
        aria-relevant="additions"
        className="mb-2 min-h-0 flex-1 overflow-y-auto pr-1"
      >
        {messages.length === 0 && (
          <p className="text-body-sm text-steel">
            Ask for a report in plain English — e.g. "resolved and handle time by Actor".
          </p>
        )}
        <div className="flex flex-col gap-3">
          {messages.map((message, index) => (
            <ChatBubble key={index} message={message} />
          ))}
        </div>
        {thinking && <ThinkingRow elapsedMs={elapsedMs} />}
        {status && !thinking && (
          <p role="status" className="mt-2 text-body-sm text-steel">
            {status}
          </p>
        )}
      </div>
      {devMode && reasoning && (
        <details className="mb-2 rounded-md border border-hairline bg-cream-soft p-2">
          <summary className="cursor-pointer text-body-sm-medium font-medium text-ink-tint">
            Raw reasoning (development only)
          </summary>
          <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap font-mono text-micro text-steel">
            {reasoning}
          </pre>
        </details>
      )}
      {/* The one-shot completion announcement (see the `announcement`
          state's docstring above) — visually hidden, so it never shows a
          redundant "Assistant replied." line beneath a bubble that already
          says as much, but present in the accessibility tree so a screen
          reader user hears it exactly once per turn. */}
      <div role="status" aria-live="polite" className="sr-only">
        {announcement}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") send();
          }}
          placeholder='e.g. "resolved and handle time by Actor"'
          disabled={busy}
          className="h-11 flex-1 rounded-md border border-hairline-strong bg-canvas px-3 text-body-sm
            text-ink outline-none transition-[border-color,box-shadow] duration-[var(--motion-base)]
            ease-brand focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:bg-cream-soft"
        />
        <button
          type="button"
          onClick={send}
          disabled={busy || !input.trim()}
          className="h-11 rounded-md bg-primary px-4 text-body-sm-medium font-medium text-on-primary
            hover:bg-primary-deep disabled:cursor-not-allowed disabled:bg-hairline-strong
            disabled:text-muted"
        >
          {busy ? "Sending…" : "Send"}
        </button>
      </div>
    </div>
  );
}

/** One turn's bubble — user and Assistant are visually distinct surfaces
 * (a plain right-aligned card for the user, a filled cream card on the
 * left for the Assistant), each carrying its Repair chips as badges
 * beneath the prose rather than inline text. */
function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={"flex flex-col " + (isUser ? "items-end" : "items-start")}>
      <span className="mb-1 text-micro-uppercase font-semibold uppercase tracking-wide text-stone">
        {isUser ? "You" : "Assistant"}
      </span>
      <div
        className={
          "max-w-full rounded-lg px-3 py-2 text-body-sm " +
          (isUser ? "border border-hairline-strong bg-canvas text-ink" : "bg-cream-soft text-ink")
        }
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.text}</p>
        ) : (
          <Markdown text={message.text} />
        )}
      </div>
      {message.chips.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {message.chips.map((chip, chipIndex) => (
            <RepairBadge key={chipIndex}>{chip}</RepairBadge>
          ))}
        </div>
      )}
    </div>
  );
}

/** A Repair/status badge (ADR-0002) — a small read-only pill, distinct from
 * the `Chip` primitive in `ui/Chip.tsx` (a selectable toggle button for the
 * builder rail, not an annotation on a message). */
function RepairBadge({ children }: { children: string }) {
  return (
    <span className="rounded-full border border-beige-deep bg-cream px-2 py-0.5 text-micro font-medium text-ink-tint">
      {children}
    </span>
  );
}

/** The thinking indicator (architecture.md §6/§7): the model reasons for
 * several seconds before its first tool call or token, and without a live
 * "still working" row the panel reads as hung rather than busy. Reappears
 * once per model call in a multi-step turn (`Chat`'s `onThinking` handler
 * just toggles this row on/off; it does not try to distinguish which call
 * it is). */
function ThinkingRow({ elapsedMs }: { elapsedMs: number }) {
  return (
    <p role="status" className="mt-2 flex items-center gap-2 text-body-sm text-steel">
      <span
        className="inline-flex h-2 w-2 animate-pulse rounded-full bg-primary"
        aria-hidden="true"
      />
      Thinking… ({(elapsedMs / 1000).toFixed(1)}s)
    </p>
  );
}
