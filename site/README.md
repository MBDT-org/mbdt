# MBDT landing page

A dependency-free static site that presents the project. No build step: the
files here are the deployable artefact. Source links point to
[github.com/MBDT-org/mbdt](https://github.com/MBDT-org/mbdt). The page deliberately
contains no install commands or environment-variable setup; those live in the
repository README.

```
site/
  index.html          the landing page
  app.js              exercise screenshot gallery
  styles.css          all styling (no framework)
  assets/logo.svg     the MBDT mark
  assets/screens/     product screenshots (captured from the running app)
  _headers            Cloudflare response headers (CSP, caching)
  robots.txt
```

## Preview locally

```bash
python3 -m http.server 8080 --directory site
# or
pnpm site:dev
```

## Deploy to Cloudflare Workers

The site is an assets-only Worker named `landing`; `wrangler.jsonc` in the
repository root points it at this `site/` directory. Nothing is compiled.

```bash
npx wrangler login     # first time only
npx wrangler deploy
```

The site is then served from `https://landing.mbdt-project.workers.dev`.
In the dashboard it is under **Workers & Pages → landing → Static assets**.

For a Git-connected deploy instead, use the same `wrangler.jsonc` and run
`npx wrangler deploy` as the deploy command (no build step).

See the Cloudflare docs for [Workers static assets](https://developers.cloudflare.com/workers/static-assets/).

## Links

Source, the MIT licence, issues and the setup guide point at
`https://github.com/MBDT-org/mbdt`. If the repository moves, update those links in
`index.html`.

If you deploy under a custom domain, update `og:url`, `og:image`, `twitter:image` and
`rel="canonical"` (currently `landing.mbdt-project.workers.dev`).
