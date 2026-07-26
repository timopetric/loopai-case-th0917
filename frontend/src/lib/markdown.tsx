import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import { Streamdown } from "streamdown";

/**
 * Renders the Assistant's prose as markdown (issue 06: frontend-rework).
 * `streamdown` is a drop-in `react-markdown` replacement purpose-built for
 * streaming: it parses completed top-level blocks once and re-parses only
 * the still-incomplete trailing block on every token, so a growing message
 * never re-renders the whole thing from scratch (the naive re-parse is
 * quadratic in message length) and finished formatting never flickers back
 * to raw syntax once a block closes.
 *
 * Model output is untrusted, so two defaults are overridden rather than
 * trusted as-is:
 *
 * 1. **Raw HTML stays disabled.** Streamdown's own default pipeline adds
 *    `rehype-raw` (parses embedded HTML tags into real elements, then
 *    relies on sanitization to strip anything dangerous). We never pass
 *    `rehype-raw` here. Streamdown detects that its `rehypePlugins` list
 *    lacks `rehype-raw` and falls back to converting HTML-looking mdast
 *    nodes into plain text instead of parsing them — a `<script>` in a
 *    reply prints as the literal string `<script>`, never as an element.
 *    This project does not depend on that fallback happening to exist;
 *    it is documented in streamdown's own source (the `Cs(...)` check in
 *    its bundle) as the intended behaviour for omitting `rehype-raw`.
 * 2. **Link protocols are allowlisted.** `rehype-sanitize`'s default schema
 *    already excludes `javascript:`, but still permits `irc(s):`/`xmpp:` —
 *    narrowed here to the three protocols a report reader could plausibly
 *    need. This is the only `rehypePlugins` entry supplied, so nothing else
 *    in the default pipeline (raw HTML, the "harden" link-confirmation
 *    modal) is reachable.
 *
 * `controls={false}` drops streamdown's copy/download chrome (code-block
 * copy button, table CSV/TSV export) — decorative affordances this panel
 * has no use for, and which style themselves against shadcn CSS variables
 * this app does not define. Turning them off keeps the rendered prose
 * inside the token layer instead of partially unstyled.
 */
const ALLOWED_LINK_PROTOCOLS = ["http", "https", "mailto"];

const SANITIZE_SCHEMA = {
  ...defaultSchema,
  protocols: {
    ...defaultSchema.protocols,
    href: ALLOWED_LINK_PROTOCOLS,
  },
};

export function Markdown({ text }: { text: string }) {
  return (
    <Streamdown controls={false} rehypePlugins={[[rehypeSanitize, SANITIZE_SCHEMA]]}>
      {text}
    </Streamdown>
  );
}
