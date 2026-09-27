# GitHub repository management

The upstream repository is [anocerino-ai/margin](https://github.com/anocerino-ai/margin). Clone it to run Margin, or create a fork when contributing. GitHub hosts source code, checks and documentation; it does not run the dashboard or Python API.

## Clone or fork

```sh
git clone https://github.com/anocerino-ai/margin.git
cd margin
```

To contribute, fork the repository in GitHub first and clone your fork instead. Add the upstream repository as a separate remote so you can pull updates. Work on a branch and open a pull request with the problem, resulting behavior and relevant validation.

## Publish an independent copy

Create an empty repository in your account without generating a README or license. Review `git remote -v` before changing remotes. To retain the existing project history and publish to your own repository:

```sh
git remote rename origin upstream
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

Use an SSH key or GitHub-supported credential manager for authentication. Never put an access token in a remote URL. Before pushing, review `git status --short` and `git diff --cached`; keep `.env`, provider overrides, databases, backups and credentials untracked. Removing a leaked credential from a file does not revoke it: replace it at its provider and inspect repository history.

## Repository settings

Enable Actions for the supplied workflows and private vulnerability reporting under Security settings. Give the repository a description explaining its editorial purpose. Keep deployment credentials in Actions secrets rather than source files.

The project checks workflow validates application code and documentation. The documentation workflow publishes MkDocs to Pages. The discovery workflow is independently controlled by `MARGIN_SCHEDULE_ENABLED`; publishing documentation does not enable discovery or consume model credits.

## Publish documentation

1. Open Settings → Pages and select **GitHub Actions** as the source.
2. Under Settings → Secrets and variables → Actions → Variables, set `MARGIN_DOCS_PAGES_ENABLED` to `true`.
3. Run **Publish documentation** from the Actions tab.
4. Wait for both build and deploy jobs to succeed, then open the deployment URL.

For your own fork, change `site_url`, `repo_url` and `repo_name` in `mkdocs.yml` to your account and repository. Project Pages normally lives under `https://YOUR_USERNAME.github.io/YOUR_REPOSITORY/`. Do not configure an application subdomain as the documentation domain unless that is intentional.

## Updates

Pull reviewed changes with `git pull --ff-only`. Run project checks before deploying an updated application. Documentation updates publish separately from the running application; a successful Pages deployment does not update Docker containers.

Reference: [GitHub Pages publishing sources](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
