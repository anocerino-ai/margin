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

In repository Settings → Pages, select GitHub Actions as the build source. Under Settings → Secrets and variables → Actions → Variables, set `MARGIN_DOCS_PAGES_ENABLED=true`, then run **Publish documentation** manually. The enable variable prevents failed deployments while Pages is unavailable. Subsequent documentation pushes to main rebuild and publish automatically. The project URL is [Margin documentation](https://anocerino-ai.github.io/margin/).

GitHub Free supports Pages from public repositories. Pages from a private repository requires an eligible plan such as GitHub Pro. Do not change repository visibility just to satisfy a deployment command without reviewing the implications. If Pages is unavailable, the strict documentation build still runs in project CI and the generated static files can be hosted elsewhere.

## Writing standards

Use English and explain each page’s purpose before giving commands. Include prerequisites, the directory where commands run, expected results and relevant recovery steps. Describe actual behavior and constraints rather than project history or a list of unfinished milestones. Cross-links provide further detail; the reader should not need another document just to understand the current page.

Use dummy addresses and placeholders in examples. Preserve versioned prompt files when editing prose documentation because stored generations may reference their hashes. Do not copy `.env`, logs, generated databases or backups into the documentation tree.

## Deployment troubleshooting

If the build job is skipped, verify the repository variable is the exact string `true`. If deployment reports that Pages is unavailable, check repository Pages settings and plan eligibility. If the site opens but nested pages or styles fail, check that `site_url` includes the repository path. Re-run the workflow after correcting settings; changing application containers does not affect the documentation site.
