# Documentation development

This site uses MkDocs with the bundled Read the Docs theme, English navigation and local search. No public documentation deployment is configured automatically.

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

The built site can be hosted as static files. A private GitHub repository does not itself guarantee that a separately deployed documentation website is private. Choose access controls before enabling GitHub Pages or another host. No `gh-deploy` command or public publishing workflow is run by this configuration.
