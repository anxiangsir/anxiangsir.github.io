# KaTeX SSR Build Skill

## Purpose

Build the static site with KaTeX formulas pre-rendered to HTML at build time so GitHub Pages serves zero runtime math-rendering JavaScript.

## Proxy Configuration

External network access on this server requires:

```bash
export http_proxy=http://172.16.5.77:8889
export https_proxy=http://172.16.5.77:8889
```

For localhost preview, bypass the proxy:

```bash
export no_proxy=127.0.0.1,localhost
```

## Build Commands

```bash
npm install
npm run build
```

## Build Output

- output directory: `dist/`
- local KaTeX assets: `dist/assets/vendor/katex/`
- source HTML remains in `pages/`

## Covered Pages

- `pages/areal.html`
- `pages/yarn.html`
- `pages/diffusion_models.html`
- `pages/verl_grpo.html`

## Build Behavior

- copy repo contents into `dist/`
- pre-render LaTeX in static HTML
- pre-render LaTeX embedded in JavaScript strings (both double-quoted and single-quoted)
- remove `katex.min.js`, `auto-render.min.js`, and `renderMathInElement(...)`
- rewrite KaTeX stylesheet links to `/assets/vendor/katex/katex.min.css`

## Verification

```bash
python -m http.server 8000 --directory dist
```

Then check:

- `/pages/areal.html`
- `/pages/yarn.html`
- `/pages/diffusion_models.html`
- `/pages/verl_grpo.html`
- `/assets/vendor/katex/katex.min.css`

All should return HTTP 200 locally.
