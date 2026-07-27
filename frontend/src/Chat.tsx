import { useEffect, useRef, useState } from "react";

import { streamAgentMessage } from "./lib/agentStream";
import { Markdown } from "./lib/markdown";
import { useReportSpecStore } from "./store/reportSpecStore";

/**
 * One turn's reasoning trace and its disclosure-panel state (issue 10,
 * ADR-0005). `reasoning` is permanent and per-message — unlike the old
 * single shared `Chat`-level `useState`, it is never wiped by the next
 * turn, and each past turn keeps its own re-expandable trace exactly as
 * `chips` already do.
 *
 * The three visual states the PRD names (Waiting / Thinking / Collapsed)
 * are *derived* from these fields at render time rather than stored as a
 * fourth redundant field:
 *   - Waiting:   !reasoningStarted && !turnDone (only meaningful on the
 *                in-flight last message; see `Chat`'s `busy` check).
 *   - Thinking:  reasoningStarted && reasoningActive (auto-expanded).
 *   - Collapsed: reasoningStarted && !reasoningActive (auto-collapsed) —
 *                its summary line still pulses if `reasoningActive` flips
 *                back true for the *next* Tool Step, and stays static once
 *                `turnDone`.
 */
interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  chips: string[];
  /** Accumulated raw reasoning text (ADR-0005: streamed to every user, in
   * every environment, unfiltered). Paragraph-broken at each Tool Step
   * boundary — see the `onThinking` "start" handler below. */
  reasoning: string;
  /** True once the first `thinking: start` has fired for this message —
   * distinguishes "no reasoning yet" (Waiting) from "reasoning arrived,
   * currently between Tool Steps" (Collapsed but not done). */
  reasoningStarted: boolean;
  /** True between a Tool Step's `thinking: start` and its `thinking: end`
   * — "that Tool Step's model call is genuinely in flight," the exact
   * condition the PRD ties the pulsing animation to. */
  reasoningActive: boolean;
  /** True once the whole turn reaches `done` or `error` — the only
   * condition allowed to make a collapsed summary line stop pulsing for
   * good, per the PRD's "collapsed but still working" vs. "collapsed and
   * finished" distinction. */
  turnDone: boolean;
  /** Current disclosure open/closed state, driven by auto-expand/collapse
   * unless `reasoningManualOverride` is set. */
  reasoningExpanded: boolean;
  /** Set the first time the user manually toggles this message's panel
   * while its Tool Step is still active. Once set, no further auto-
   * expand/auto-collapse transition may touch `reasoningExpanded` for this
   * message — only a brand new turn (a brand new `ChatMessage`) starts
   * fresh with this false again. */
  reasoningManualOverride: boolean;
}

/** The reasoning fields are only ever populated on assistant messages, but
 * live on the shared `ChatMessage` type (like `chips` already did) rather
 * than a discriminated union, matching this component's existing style —
 * `newUserMessage` just fills them with their inert defaults. */
function newUserMessage(text: string): ChatMessage {
  return {
    role: "user",
    text,
    chips: [],
    reasoning: "",
    reasoningStarted: false,
    reasoningActive: false,
    turnDone: false,
    reasoningExpanded: false,
    reasoningManualOverride: false,
  };
}

function newAssistantMessage(): ChatMessage {
  return {
    role: "assistant",
    text: "",
    chips: [],
    reasoning: "",
    reasoningStarted: false,
    reasoningActive: false,
    turnDone: false,
    reasoningExpanded: false,
    reasoningManualOverride: false,
  };
}

/**
 * The empty-state greeting (issue 11) — hard-coded, no model call, no
 * tokens, rendered through the same `Markdown` pipeline as a real reply so
 * its bullets/formatting go through the one sanitized renderer rather than
 * a second, parallel plain-JSX path. Its job is discovery: the product
 * owner found the pivot-layout capability only by accident, so this leads
 * with it and follows with concrete, literal "try:" sentences a user could
 * actually type — not abstract feature descriptions. Vocabulary stays in
 * Actor/Mailbox terms (CONTEXT.md); no tool name or wire enum value.
 */
const GREETING = `I turn plain English into a report — pick metrics, group by Actor or Mailbox, reshape the layout, or narrow it down to one person.

- try: put the dates across the top and the metrics down the side
- try: filter to just Theo's numbers
- try: chart average handle time by Mailbox instead of a table
- try: show me last week grouped by Actor

What report would you like to build?`;

/**
 * The Assistant chat panel (issue 15; docked as `AssistantPane` in issue
 * 02; markdown + visual pass in issue 06; per-message reasoning trace in
 * issue 10). Renders the presenter's small, fixed vocabulary — a thinking
 * row with an elapsed counter, chips as badges on the Assistant's message,
 * a per-message reasoning trace (ADR-0005), and streamed prose rendered as
 * markdown (architecture.md §6, §7). Never touches a tool name or raw
 * argument — those never arrive here in the first place, since
 * `app/agent/presenter.py` is the chokepoint that keeps them off the wire;
 * this component only *formats* what already arrives (`lib/markdown.tsx`'s
 * docstring covers the markdown-specific half of that guarantee). The one
 * exception, by design, is the reasoning trace itself: ADR-0005 accepts
 * that a reasoning model's chain-of-thought routinely names tool/enum
 * internals, and renders it unfiltered in its own labelled panel — that
 * tradeoff applies to the model's streamed content only, never to the
 * chrome this component writes around it (labels, summary lines stay in
 * Actor/Mailbox/Assistant vocabulary).
 *
 * Reads and writes the single Report Spec store (`store/reportSpecStore.ts`)
 * directly rather than taking a spec via props: `buildSpec()` is the exact
 * spec the on-screen builder currently shows, sent as the starting point for
 * the Assistant's next turn (architecture.md §6: "a POST carrying state");
 * `applySpec` is called on every `spec` event, so the controls visibly move
 * one field at a time as the Assistant works (user story 38, ADR-0002) —
 * through the SAME store `BuilderPane`'s controls edit.
 */
export function Chat() {
  const buildSpec = useReportSpecStore((state) => state.buildSpec);
  const applySpec = useReportSpecStore((state) => state.applySpec);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [status, setStatus] = useState<string | null>(null);

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
    setMessages((prev) => [...prev, newUserMessage(text), newAssistantMessage()]);

    function updateLastAssistantMessage(update: (message: ChatMessage) => ChatMessage) {
      setMessages((prev) => {
        const next = [...prev];
        const lastIndex = next.length - 1;
        next[lastIndex] = update(next[lastIndex]);
        return next;
      });
    }

    /** Auto-expand/auto-collapse a message's reasoning panel — a no-op once
     * `reasoningManualOverride` is set, per the PRD's manual-override rule:
     * a mid-turn manual toggle is never snapped back by the next auto
     * transition for that same message. */
    function setExpandedUnlessOverridden(message: ChatMessage, expanded: boolean): ChatMessage {
      return message.reasoningManualOverride ? message : { ...message, reasoningExpanded: expanded };
    }

    try {
      await streamAgentMessage(text, buildSpec(), {
        onThinking: (event) => {
          if (event.state === "start") {
            setThinking(true);
            startThinkingTimer();
            updateLastAssistantMessage((message) =>
              setExpandedUnlessOverridden(
                {
                  ...message,
                  // Segmentation: a paragraph break before this Tool
                  // Step's reasoning, but only if a previous Tool Step
                  // already left text behind — the first burst needs no
                  // leading separator.
                  reasoning: message.reasoning ? message.reasoning + "\n\n" : message.reasoning,
                  reasoningStarted: true,
                  reasoningActive: true,
                },
                true,
              ),
            );
          } else {
            setThinking(false);
            stopThinkingTimer();
            updateLastAssistantMessage((message) =>
              setExpandedUnlessOverridden({ ...message, reasoningActive: false }, false),
            );
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
          updateLastAssistantMessage((message) =>
            setExpandedUnlessOverridden({ ...message, reasoningActive: false, turnDone: true }, false),
          );
        },
        onError: (event) => {
          setStatus(null);
          setThinking(false);
          stopThinkingTimer();
          setBusy(false);
          updateLastAssistantMessage((message) =>
            setExpandedUnlessOverridden(
              { ...message, text: message.text || event.text, reasoningActive: false, turnDone: true },
              false,
            ),
          );
          setAnnouncement("Assistant could not complete the reply.");
        },
        onThinkingText: (event) => {
          updateLastAssistantMessage((message) => ({
            ...message,
            reasoning: message.reasoning + event.text,
          }));
        },
      });
    } finally {
      setBusy(false);
      setThinking(false);
      stopThinkingTimer();
    }
  }

  /** Manual override (PRD "Manual override"): flips `reasoningExpanded` and
   * latches `reasoningManualOverride` so no subsequent auto transition for
   * this message can undo the user's choice. Applies to any message, not
   * just the in-flight one — past turns' panels are freely re-expandable
   * (PRD acceptance criterion) and re-collapsing one is just as much a
   * manual choice, harmless to latch since a finished turn has no more
   * auto transitions left to suppress. */
  function toggleReasoningPanel(index: number) {
    setMessages((prev) => {
      const next = [...prev];
      const message = next[index];
      next[index] = {
        ...message,
        reasoningExpanded: !message.reasoningExpanded,
        reasoningManualOverride: true,
      };
      return next;
    });
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
          <div className="text-body-sm text-steel">
            <Markdown text={GREETING} />
          </div>
        )}
        <div className="flex flex-col gap-3">
          {messages.map((message, index) => (
            <ChatBubble
              key={index}
              message={message}
              busy={busy && index === messages.length - 1}
              // The elapsed-time counter belongs to whichever Tool Step is
              // actually running right now, which can only ever be the
              // last message — passing it to every bubble would either
              // show a stale, frozen number on a past turn's panel (the
              // counter is never reset for those) or make one restart from
              // 0 every re-render. `ReasoningPanel` also only displays it
              // while that same message's `reasoningActive` is true, so a
              // past turn's collapsed summary never shows a number at all.
              elapsedMs={index === messages.length - 1 ? elapsedMs : undefined}
              onToggleReasoning={() => toggleReasoningPanel(index)}
            />
          ))}
        </div>
        {status && !thinking && (
          <p role="status" className="mt-2 text-body-sm text-steel">
            {status}
          </p>
        )}
      </div>
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
            hover:bg-primary-deep disabled:cursor-not-allowed disabled:bg-hairline
            disabled:text-stone"
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
 * beneath the prose rather than inline text. The Assistant's bubble also
 * carries its reasoning trace (issue 10) — `busy` is true only for the
 * last message while a turn is in flight, which is what makes the Waiting
 * state ("no reasoning yet") distinguishable from a past, already-silent
 * turn that simply never streamed any reasoning. */
function ChatBubble({
  message,
  busy,
  elapsedMs,
  onToggleReasoning,
}: {
  message: ChatMessage;
  busy: boolean;
  elapsedMs?: number;
  onToggleReasoning: () => void;
}) {
  const isUser = message.role === "user";
  return (
    <div className={"flex flex-col " + (isUser ? "items-end" : "items-start")}>
      <span className="mb-1 text-micro-uppercase font-semibold uppercase tracking-wide text-stone">
        {isUser ? "You" : "Assistant"}
      </span>
      {!isUser && busy && !message.reasoningStarted && (
        <p className="mb-1 text-body-sm text-steel">Waiting for a response…</p>
      )}
      {!isUser && message.reasoningStarted && (
        <ReasoningPanel message={message} elapsedMs={elapsedMs} onToggle={onToggleReasoning} />
      )}
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

/** The per-message reasoning trace panel (issue 10, ADR-0005) — Thinking
 * and Collapsed are the same `<details>` element, distinguished only by
 * `message.reasoningExpanded` and whether the dot keeps pulsing. This is
 * also where the old standalone `ThinkingRow`'s elapsed-time counter now
 * lives: before this slice, a Tool Step in flight showed *two* pulsing
 * dots on screen at once — one on this panel's summary, one on
 * `ThinkingRow` below the message list — and the second one had nothing
 * behind it. Folding the counter into this summary line leaves exactly one
 * indicator, which says it is thinking, how long for, and (on expand) what
 * about.
 *
 * `elapsedMs` is only ever passed for the single last, in-flight message
 * (`Chat`'s render loop) and only ever displayed while `reasoningActive` is
 * true — a past turn's panel, or a gap between this turn's Tool Steps, must
 * never show a stale or restarting number.
 *
 * Native `<details>` toggling is intercepted (`preventDefault` on the
 * `<summary>` click) rather than trusted, because open/closed state here
 * is also driven by auto-expand/auto-collapse from stream events — letting
 * the DOM and React state diverge would make the manual-override rule
 * (`reasoningManualOverride`) unenforceable. */
function ReasoningPanel({
  message,
  elapsedMs,
  onToggle,
}: {
  message: ChatMessage;
  elapsedMs?: number;
  onToggle: () => void;
}) {
  const pulsing = message.reasoningActive;
  const showElapsed = message.reasoningActive && typeof elapsedMs === "number";
  return (
    <details
      open={message.reasoningExpanded}
      className="mb-1 w-full rounded-md border border-hairline bg-cream-soft p-2"
    >
      <summary
        role="status"
        onClick={(event) => {
          event.preventDefault();
          onToggle();
        }}
        className="flex cursor-pointer items-center gap-2 text-body-sm-medium font-medium text-ink-tint"
      >
        <span
          className={"inline-flex h-2 w-2 rounded-full bg-primary" + (pulsing ? " animate-pulse" : "")}
          aria-hidden="true"
        />
        Thinking{showElapsed ? ` (${(elapsedMs / 1000).toFixed(1)}s)` : ""}
      </summary>
      <div className="mt-1 max-h-64 overflow-auto text-micro text-steel">
        <Markdown text={message.reasoning} />
      </div>
    </details>
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
