# Design system: Arterion ECG Monitor

A recreation of a clean medical-AI landing page, in violet and white. Every claim and number on the page comes from this project's own README and metrics.

## Structure
1. Floating navigation: logo mark, pill tabs, status, sign-in, Get Started
2. Hero: badge, serif headline (italic gradient second line), lead, two calls to action, check-badges, motif line
3. Features: six cards with gradient icon tiles
4. Process: four numbered steps joined by a rail that fills as you scroll
5. Analyze: the working tool
6. Evidence: dark section with an italic claim and a glass panel of held-out metric bars
7. Call to action and footer

## Tokens
| Token | Value |
|---|---|
| `--brand-1` | `#5b21b6` |
| `--brand-2` | `#7c3aed` |
| `--brand-3` | `#8b5cf6` |
| `--bright` | `#c4b5fd` |
| `--ink` | `#1e1b4b` |
| `--muted` | `#6b6890` |
| `--bg` | `#faf9ff` |
| `--soft` | `#f5f3ff` |
| `--dark-1` | `#150f33` |
| `--dark-2` | `#3b1d8f` |

## Type
Headlines: 'DM Serif Display'. Body: 'Plus Jakarta Sans'. Numbers: 'IBM Plex Mono'.

## Motion
- **Motion (framer-motion engine, vanilla build):** hero entrance on a spring, button hover and press springs, count-ups.
- **GSAP + ScrollTrigger:** read-progress bar, hero parallax, heading and card reveals, a scrubbed rail that connects the steps, metric bars that grow once in view.
- **Reduced motion:** all animation is skipped and bars and counters show their final values.

## Dark mode
Dark tokens override the light ones under `html[data-theme="dark"]`, and under `prefers-color-scheme: dark` when no choice has been saved. Surfaces: `--bg #0d0b1c`, `--soft #121030`, `--card #17142f`; text `--ink #ece9ff`; links `--link #c4b5fd`. The toggle remembers the choice in `localStorage` and a script in `<head>` applies it before first paint, so there is no flash. The evidence section is dark in both themes.

## Accessibility
Skip link, labelled landmarks, visible focus rings, text contrast of at least 4.5:1 on buttons, and a keyboard-operable mobile menu.
