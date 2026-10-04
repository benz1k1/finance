Third-party static assets vendored here — no CDN at runtime, no bundler, no build step.

- `tailwind.js` — Tailwind CSS 3.4.17 "Play CDN" browser build. JIT-compiles utility classes by
  scanning the DOM. This is Tailwind's zero-build-step mode: right for an internal admin tool,
  and explicitly not what Tailwind recommends for a public site (it ships the whole compiler and
  purges nothing). If this package ever grows a real frontend build, swap it for a CLI build.
- `daisyui.full.min.css` — daisyUI 4.12.24, precompiled, all components and themes. Independent
  of Tailwind's JIT: daisyUI's classes (`btn`, `card`, `table`, …) are plain CSS, and Tailwind is
  only used for utilities on top of them.
- `mdi/` — Material Design Icons webfont, used as `<i class="mdi mdi-…">`. Note `mdi/css` and
  `mdi/fonts` are **nested**: a flat `static/*` glob in the packaging misses the font files, and
  the page then renders every icon as a blank box.
- `alpine.min.js` — Alpine.js 3.14.9 (MIT). Client-only interactivity: a disclosure, a dropdown,
  a form's loading state.
- `htmx.min.js` — htmx 2.0.4 (BSD-2-Clause). Everything server-synced: filters, live fragments,
  the ingest wizard's progress poll.
