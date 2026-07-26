import { fetchEventSource } from "@microsoft/fetch-event-source";

import { getStoredApiKey } from "./apiKey";
import type { ReportSpec } from "./report";

/**
 * Mirrors `app/agent/events.py`'s presenter-event vocabulary exactly
 * (issue 15, architecture.md §6) — the ONLY shapes the backend ever sends
 * over this stream. There is deliberately no `tool_name`/`args`/`prompt`
 * field anywhere here: the presenter is the chokepoint that keeps those out
 * (AGENTS.md), so there is nothing for the frontend types to even carry.
 */
export interface ThinkingEvent {
  state: "start" | "end";
  ms?: number;
}
export interface StatusEvent {
  text: string;
}
export interface ChipsEvent {
  chips: string[];
}
export interface SpecEvent {
  spec: ReportSpec;
}
export interface TokenEvent {
  text: string;
}
export interface DoneEvent {
  summary: string;
  spec_version: number;
}
export interface ErrorEvent {
  text: string;
}
/** Dev-only: raw reasoning text (architecture.md §6 "Dev-mode exception").
 * The backend only ever sends this event when `settings.is_development` —
 * the frontend does not need its own environment check, it renders
 * whatever it receives into the collapsible panel. */
export interface ThinkingTextEvent {
  text: string;
}

export interface AgentStreamHandlers {
  onThinking?: (event: ThinkingEvent) => void;
  onStatus?: (event: StatusEvent) => void;
  onChips?: (event: ChipsEvent) => void;
  onSpec?: (event: SpecEvent) => void;
  onToken?: (event: TokenEvent) => void;
  onDone?: (event: DoneEvent) => void;
  onError?: (event: ErrorEvent) => void;
  onThinkingText?: (event: ThinkingTextEvent) => void;
}

/**
 * Stream one Assistant turn (issue 15). `POST`, not `GET` + native
 * `EventSource`: the request carries the message and the current Report
 * Spec, and auth needs the same `X-API-Key` header every other route uses,
 * which `EventSource` cannot set (architecture.md §6) — `fetchEventSource`
 * gives POST + headers + SSE parsing together.
 *
 * One stream per message (architecture.md §6: "request-scoped, no long-
 * lived socket to babysit") — this function resolves once the stream ends,
 * it does not retry, matching the `onerror` handler below, which always
 * re-throws to stop `fetchEventSource`'s built-in retry loop.
 */
export async function streamAgentMessage(
  message: string,
  spec: ReportSpec,
  handlers: AgentStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const apiKey = getStoredApiKey();

  await fetchEventSource("/api/v1/agent/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(apiKey ? { "X-API-Key": apiKey } : {}),
    },
    body: JSON.stringify({ message, spec }),
    signal,
    async onopen(response) {
      if (!response.ok) {
        throw new Error(`agent stream failed to open: ${response.status}`);
      }
    },
    onmessage(event) {
      const data = event.data ? JSON.parse(event.data) : {};
      switch (event.event) {
        case "thinking":
          handlers.onThinking?.(data as ThinkingEvent);
          break;
        case "status":
          handlers.onStatus?.(data as StatusEvent);
          break;
        case "chips":
          handlers.onChips?.(data as ChipsEvent);
          break;
        case "spec":
          handlers.onSpec?.(data as SpecEvent);
          break;
        case "token":
          handlers.onToken?.(data as TokenEvent);
          break;
        case "done":
          handlers.onDone?.(data as DoneEvent);
          break;
        case "error":
          handlers.onError?.(data as ErrorEvent);
          break;
        case "thinking_text":
          handlers.onThinkingText?.(data as ThinkingTextEvent);
          break;
        default:
          // An event name outside the known vocabulary is dropped, not
          // guessed at — the presenter is the only source of truth for what
          // this stream can say (architecture.md §6).
          break;
      }
    },
    onerror(err) {
      handlers.onError?.({ text: "Lost connection to the assistant." });
      throw err; // re-throw: stop fetchEventSource's automatic retry
    },
  });
}
