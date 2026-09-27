# Documentation development

This site uses MkDocs with the bundled Read the Docs theme, English navigation and local search. The Publish documentation workflow builds and deploys this site to GitHub Pages.

## Install and preview

From the repository root:

```sh
python3.12 -m venv .venv-docs
.venv-docs/bin/pip install -r requirements-docs.txt
.venv-docs/bin/mkdocs serve
```

Open <http://127.0.0.1:8001>. Port 8001 avoids the API's development port. Documentation dependencies are isolated from application runtime dependencies.

## Validate and build

```sh
.venv-docs/bin/mkdocs build --strict
```

Output is written to `site/`, which is ignored by Git. CI runs the same strict build: broken internal links, unknown anchors and missing navigation entries fail validation. This checks internal documentation structure, not the availability of external websites.

Add Markdown pages under `docs/` and register them in `mkdocs.yml`. Keep operational instructions reproducible, secrets out of examples and current limitations explicit.

## Hosting

The built site can be hosted as static files. A private GitHub repository does not itself guarantee that a separately deployed documentation website is private. Choose access controls before enabling GitHub Pages or another host. The workflow publishes only the generated `site/` artifact, with deployment permissions restricted to its deploy job. Enable GitHub Pages with GitHub Actions as its source. A private repository needs an eligible GitHub plan for Pages; the published website can be public even though source access remains private.

## Enable deployment

In repository Settings → Pages, select GitHub Actions as the build source. Under Settings → Secrets and variables → Actions → Variables, set `MARGIN_DOCS_PAGES_ENABLED=true`, then run **Publish documentation** manually. The enable variable prevents failed deployments while Pages is unavailable. Subsequent documentation pushes to main rebuild and publish automatically. The expected project URL is https://anocerino-ai.github.io/margin/.

GitHub Free supports Pages from public repositories. Pages from this private repository requires an eligible plan such as GitHub Pro. Do not change repository visibility just to satisfy a deployment command without reviewing the implications. If Pages is unavailable, the strict documentation build still runs in project CI and the generated static files can be hosted elsewhere.
