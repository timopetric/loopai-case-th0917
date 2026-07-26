import { useEffect, useRef, useState } from "react";

import { streamAgentMessage } from "./lib/agentStream";
import type { ReportSpec } from "./lib/report";

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
  chips: string[];
}

interface ChatProps {
  /** The exact spec the on-screen builder currently shows — sent as the
   * starting point for the Assistant's next turn (architecture.md §6: "a
   * POST carrying state"). */
  spec: ReportSpec;
  /** Applies a full spec to the SAME store the builder controls edit
   * (`App.tsx`'s `applySpec`) — called on every `spec` event, so the
   * controls visibly move one field at a time as the Assistant works
   * (user story 38, ADR-0002). */
  onApplySpec: (spec: ReportSpec) => void;
}

/**
 * The Assistant chat panel (issue 15). Renders the presenter's small, fixed
 * vocabulary — a thinking row with an elapsed counter, chips as tags on the
 * Assistant's message, and streamed prose (architecture.md §6, §7). Never
 * touches a tool name, a raw argument or reasoning text outside the
 * dev-only panel below — those never arrive here in the first place, since
 * `app/agent/presenter.py` is the chokepoint that keeps them off the wire.
 */
export function Chat({ spec, onApplySpec }: ChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [status, setStatus] = useState<string | null>(null);
  /** Raw reasoning text, dev-only (architecture.md §6 "Dev-mode
   * exception") — populated only if the backend ever sends a
   * `thinking_text` event, which it only does when `settings.is_development`.
   * A non-empty value is therefore itself the signal to show the panel; no
   * separate environment flag needs to travel to the frontend. */
  const [reasoning, setReasoning] = useState("");

  const timerRef = useRef<number | null>(null);
  const thinkingStartRef = useRef<number | null>(null);
  const specRef = useRef(spec);
  specRef.current = spec;

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
      await streamAgentMessage(text, specRef.current, {
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
        onSpec: (event) => onApplySpec(event.spec),
        onToken: (event) => {
          updateLastAssistantMessage((message) => ({
            ...message,
            text: message.text + event.text,
          }));
        },
        onDone: () => {
          setStatus(null);
          setBusy(false);
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
    <section style={{ marginTop: "2rem", maxWidth: 520 }}>
      <h2>Assistant</h2>
      <div
        role="log"
        style={{
          border: "1px solid #ccc",
          borderRadius: 4,
          padding: "0.75rem",
          minHeight: 100,
          marginBottom: "0.5rem",
        }}
      >
        {messages.length === 0 && (
          <p style={{ color: "#888", margin: 0 }}>
            Ask for a report in plain English — e.g. "resolved and handle time by agent".
          </p>
        )}
        {messages.map((message, index) => (
          <div key={index} style={{ marginBottom: "0.5rem" }}>
            <strong>{message.role === "user" ? "You" : "Assistant"}:</strong> {message.text}
            {message.chips.length > 0 && (
              <div style={{ marginTop: "0.25rem" }}>
                {message.chips.map((chip, chipIndex) => (
                  <span
                    key={chipIndex}
                    style={{
                      display: "inline-block",
                      background: "#e7f1ff",
                      color: "#084298",
                      borderRadius: 12,
                      padding: "0.1rem 0.6rem",
                      marginRight: "0.3rem",
                      marginTop: "0.2rem",
                      fontSize: "0.8rem",
                    }}
                  >
                    {chip}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {thinking && (
          <p role="status" style={{ fontStyle: "italic", color: "#666", margin: 0 }}>
            Thinking… ({(elapsedMs / 1000).toFixed(1)}s)
          </p>
        )}
        {status && !thinking && (
          <p role="status" style={{ color: "#666", margin: 0 }}>
            {status}
          </p>
        )}
      </div>
      {reasoning && (
        <details style={{ marginBottom: "0.5rem" }}>
          <summary>Raw reasoning (development only)</summary>
          <pre
            style={{
              whiteSpace: "pre-wrap",
              fontSize: "0.75rem",
              background: "#f6f6f6",
              padding: "0.5rem",
              maxHeight: 200,
              overflow: "auto",
            }}
          >
            {reasoning}
          </pre>
        </details>
      )}
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") send();
          }}
          placeholder='e.g. "resolved and handle time by agent"'
          disabled={busy}
          style={{ flex: 1 }}
        />
        <button type="button" onClick={send} disabled={busy || !input.trim()}>
          Send
        </button>
      </div>
    </section>
  );
}
