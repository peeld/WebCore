# core/

This directory (and `modules/`) is **shared** — it's the `WebCore` git submodule, reused
as-is across every site built on this template. Nothing site-specific (branding, copy,
API keys, enabled-module list) belongs in here. See `../ARCHITECTURE.md` for the full
module system; this file covers the split between shared template code and per-site
content, for anyone standing up a new site on the template.

## Shared vs. per-site

| Lives in | What it is | Git |
|---|---|---|
| `core/` | This repo — Django project, React app shell, install tooling | submodule `WebCore` |
| `modules/` | Feature modules (billing, userauth, booking, ...) | submodule `WebModules` |
| `site/` | This deployment's own content — branding, marketing copy, site-only routes | part of the site's own top-level repo, **not** a submodule |
| `modules.json` (repo root) | Which modules this site has enabled | part of the site's own top-level repo |

A new site is a fresh top-level repo that adds `core` and `modules` as submodules,
creates `modules.json` and `site/`, and otherwise doesn't need to touch `core/` or
`modules/` at all.

## What a new site must provide in `site/`

### `site/frontend/public/` (required)

Branding assets: `favicon.ico`, `logo.png`, `logo-dark.png`, `navicon.png`. `install.py`
symlinks `core/frontend/public` → `site/frontend/public`, so these are served exactly
like any other Vite public asset.

### `site/frontend/theme.css` (required)

Brand color, typography, and font loading. Imported once, by
`core/frontend/src/index.css` — replace this file's contents for your brand, don't edit
`index.css` itself.

### `site/frontend/src/index.js` (optional)

If this file exists, `install.py` treats `site/` as a **pseudo-module**: `regen` wires it
into the generated `core/frontend/src/modules.js` as `siteModule`, spliced in ahead of
every installed module (same slot order as modules, just first). It uses the same export
shape as a module's `index.js` — export whichever of these your site needs:

```js
export const routes = [];        // React Router route definitions
export const navItems = [];      // Navbar links
export const providers = [];     // Context providers wrapped around the app tree
export const navbarEnd = [];     // Components in the Navbar's right slot
export const adminCards = [];    // Cards on /admin
export const userSections = [];  // Cards on /dashboard
export const homeSections = [];  // Declarative homepage ("/") layout — see below
export const HomePage = undefined; // Full homepage component override — see below
```

Components under `site/frontend/src/` can import shared core code via the
`@core/frontend/...` alias, the same as any module (e.g.
`@core/frontend/components/SiteLogo.jsx`). No `module.json` is needed — `site/` isn't a
real module and doesn't go through the `requires`/dependency graph.

#### `homeSections`: the site owns the homepage layout

Modules don't put anything on the homepage on their own. A module that has something to
offer the homepage exports a `homeWidgets` map instead of `homeSections` — a namespaced
registry of configurable components, not a rendered list:

```js
// modules/billing/frontend/src/index.js
export const homeWidgets = { featuredProducts: FeaturedProducts };
```

`install.py` collects every enabled module's `homeWidgets` into `moduleHomeWidgets` in
the generated `modules.js`, keyed by module name (`{ billing: { featuredProducts: ... },
booking: { upcomingEvents: ... } }`). Nothing renders from that registry by itself.

The site's own `homeSections` array is the actual homepage layout — a list of entries
rendered top to bottom, in order. Each entry is either a plain component (site-owned
content) or a `{ widget: '<module>.<key>', props }` reference that pulls a component out
of `moduleHomeWidgets` and renders it with the given props:

```js
// site/frontend/src/index.js
export const homeSections = [
  BannerSection,                                        // site's own component
  AboutSection,
  { widget: 'billing.featuredProducts', props: { limit: 6 } },
  { widget: 'booking.upcomingEvents' },                 // uses the widget's own defaults
];
```

A module's widget only appears if the site's `homeSections` references it — enabling a
module does not, by itself, add anything to the homepage. A site with no `index.js` (or
one that omits `homeSections`) gets an empty homepage (via core's default `HomePage`,
below). This is deliberate: modules publish configurable units, the site decides what
appears, in what order, and with what configuration.

#### `HomePage`: escaping the declarative layout entirely

`homeSections` covers ordering and configuring widgets, but it's still core's generic
`HomePage.jsx` doing the rendering. If a site needs more than that — custom markup
between sections, conditional sections based on site-specific state, widgets composed
with site-only components in a layout `homeSections` can't express — it can export its
own `HomePage` component instead:

```js
// site/frontend/src/index.js
import { moduleHomeWidgets } from '@core/frontend/modules.js';

const { featuredProducts: FeaturedProducts } = moduleHomeWidgets.billing;

export function HomePage() {
  return (
    <>
      <BannerSection />
      <FeaturedProducts limit={6} title="Just In" />
      <AboutSection />
    </>
  );
}
```

A custom `HomePage` can reach a module's widgets either through `moduleHomeWidgets`
(re-exported from `@core/frontend/modules.js`, the same registry `homeSections`
resolves against) or by importing a module directly (`import * as billing from
'@modules/billing'`) for anything else the module exports. `install.py` wires
`siteModule.HomePage` into the generated `modules.js` as `siteHomePage`; `App.jsx` uses
it for the `/` route when present, and falls back to core's own `HomePage.jsx` (the
`homeSections`-driven default) otherwise. A site only needs one of `homeSections` or
`HomePage` — `HomePage`, if exported, takes full control and `homeSections` is ignored.

Run `python core/install.py regen` after adding or changing this file (or anything in
`site/frontend/src/`) — `modules.js` is generated and must never be hand-edited.

Nothing under `site/frontend/src/` is required. A site with no homepage copy, no custom
routes, and no site-only sections can simply omit `index.js`; `install.py` skips wiring
it in.

### Per-site env & secrets

Not part of `site/`, but per-deployment the same way:

- `core/frontend/.env` (`.env.development` / `.env.production`) — `VITE_APP_NAME`,
  `VITE_APP_ICON`, `VITE_APP_ICON_DARK`, `VITE_API_URL`, etc. Copy from
  `core/frontend/.env.example`; gitignored inside the `core` submodule itself, so every
  site creates its own and it's never committed.
- `core/backend/.env` and `core/backend/secrets.json` — Django `SECRET_KEY`, third-party
  API keys. Same pattern: copy from the `.env.example` / `secrets.json.example` in that
  directory, gitignored, never committed.
- `modules.json` (site repo root) — the list of module names this deployment enables.
  Edited directly (or via `python core/install.py add/remove <module>`, which keeps it in
  sync).

## Rules for anyone editing `core/` or `modules/` itself

- Changes here ship to **every** site on the next submodule bump — never hardcode a
  site's name, copy, colors, or API keys.
- If something is genuinely deployment-specific, it belongs in `site/` (or a per-site env
  var), not behind a flag in `core/`.
- See `../ARCHITECTURE.md` and `../CLAUDE.md` for the module conventions (isolation,
  `api.js`-only fetches, `install.py`-managed manifests, etc.) that apply to both
  `core/` and every module in `modules/`.
