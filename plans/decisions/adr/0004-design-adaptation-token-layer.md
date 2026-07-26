# Adapt the Mistral design reference into a token layer; brand colour stays out of the chart palette

`design-reference-mistral.md` documents a marketing site: an 84px hero over photography, a
sunset-gradient closing band, and a licensed display face (`PP Editorial Old`) over a saturated
orange primary and sunshine-yellow family. This app is a data-dense analytical tool people stare
at rather than glance at, so the reference is adapted, not copied, per the frontend-rework PRD's
"Design adaptation" table. This ADR is the record of that adaptation and, separately, of the one
genuine conflict between the reference and `architecture.md` §7's chart rules.

**Colour.** The reference's cream family (`#fff8e0`) is kept but demoted to an **accent**
surface — rails, cards, banners (the sign-in card, in this slice). The **data surface stays
white** (`--color-canvas`): behind thousands of scanned table cells, cream lowers contrast and
tires the eye in a way it never would on a page someone reads once and leaves. The saturated
orange primary (`#fa520f`) is kept for CTAs and active states only, exactly as the reference's own
component notes prescribe ("keep `{colors.primary}` confined to primary CTAs, active states") —
and, on top of that, **it must never enter the chart series palette**. `architecture.md` §7 fixes
that palette as eight entity-stable, CVD-safe hues chosen by the dataviz skill; flooding the UI
with the brand orange, or admitting it as one of the eight, would destroy series distinctiveness
the moment a report happens to colour a series orange next to a CTA that is also orange. Brand
colour and chart colour are disjoint sets by construction, not by convention.

**Type.** `PP Editorial Old` is a commercial licence; `Instrument Serif` (OFL) replaces it
one-for-one, restricted to the same *display* sizes the reference used it for (`display-lg`,
`heading-1`, `stat-display`) — never body text, where a serif at 14–16px reads as filler article
copy, not report content. Inter (OFL) covers everything else. JetBrains Mono (OFL) is added for
tabular figures, which the reference doesn't need (it has no data tables) but this app does. The
84px `hero-display` size is dropped outright — there is no hero.

**Layout decoration.** The hero, the sunset gradient/stripe band, and the photography are all
dropped. None have a place in a report builder; the reference itself calls the "Known Gaps"
category out separately from its core system, and none of the dropped items are in it.

**Dark mode.** The reference lists "no dark-mode tokens" as a known gap. A ramp is derived here
(the `prefers-color-scheme: dark` overrides in `tokens.css`) since this app needs dark mode; the
chart palette itself is a **selected** set of steps validated against the dark surface, not an
automatic inversion of the light palette (§7) — inverting risks CVD-unsafe pairs that were never
validated for the pairs actually produced.

**Fonts are self-hosted, not CDN-linked.** All three families are vendored as `.woff2` files under
`frontend/src/assets/fonts/` and referenced by local, relative `url()` — Vite fingerprints and
bundles them, so there is no request to any external host at runtime. A CDN link would add an
external runtime dependency that behaves identically in development and differently in
production after a build, which is the exact class of mistake `AGENTS.md`'s
no-build-time-configuration rule exists to prevent, even though a font link isn't itself a
`VITE_*` value.

## Considered Options

- **Apply the reference literally** (cream page background, `PP Editorial Old`, hero, gradient
  band). Rejected: cream-behind-thousands-of-cells fails a real legibility test, the display face
  can't ship, and there is no hero to speak of in this product.
- **Keep the reference's saturated orange in the chart palette**, since it's visually distinctive
  and already licensed for use. Rejected: it collides with the CTA colour the moment a report
  contains a series that happens to land on that hue, and it isn't chosen for CVD-safety the way
  the dataviz skill's eight-hue set is — chart colour needs to be *selected*, not *reused*.
- **Register the named spacing scale (`xxs`…`xxxl`) as Tailwind `@theme` tokens**, mirroring the
  reference's own key names one-for-one. Tried first, and reverted: Tailwind v4 resolves sizing
  utilities (`w-*`, `h-*`, `max-w-*`, `gap-*`, …) against the `--spacing-*` namespace before any
  utility-specific fallback, so a custom `--spacing-sm: 0.75rem` silently replaced the built-in
  `max-w-sm` (24rem) with 12px everywhere `sm` was used as a size, not just as spacing — an actual
  regression the build caught (`max-w-sm` shrank the sign-in card to a sliver). The named scale is
  kept as documentation only; production classes use Tailwind's own numeric spacing utilities
  (`p-8`, `mt-5`, …), which map onto the same 4px-multiple values without colliding with any other
  namespace.
- **No dark ramp in this slice**, deferring it until a screen actually needs dark mode. Rejected:
  the token layer is the one place a ramp is cheap to derive correctly (redefine the surface/ink
  custom properties under one media query) and expensive to retrofit once colour values are
  scattered through components that reference the light hex directly.

## Consequences

- Every later slice reaches for a Tailwind utility class backed by a token (`bg-cream`,
  `text-ink`, `rounded-lg`, `font-display`) instead of a raw hex value; `tokens.css` is the single
  place a colour, radius, or display-size value is spelled out literally.
- The named spacing scale in `tokens.css`'s closing comment (`xxs`→`p-1` … `section`→`p-16`) is
  the contract between the reference's vocabulary and the numeric classes actually used; a
  reviewer diffing against the reference should read that mapping, not expect `p-sm` to exist as
  a class.
- Chart colour selection is out of scope for this slice (deferred to whichever slice builds the
  chart), but the constraint that brand colour is excluded from it is fixed now, before any chart
  code exists to violate it.
- The four font files are vendored, not fetched: `instrument-serif-regular.woff2`,
  `instrument-serif-italic.woff2`, `inter-variable.woff2` (variable, weights 400–700 in one file),
  and `jetbrains-mono-variable.woff2` (variable, weights 400–600 in one file). Sourced from Google
  Fonts' own OFL-licensed distributions, latin subset only.
