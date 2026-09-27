# Publish the repository

1. Sign in to [GitHub](https://github.com) and [create a repository](https://github.com/new) named `margin`. Start private if you want to review it before making it public. Leave README, license and gitignore initialization unchecked: this project already contains those files.
2. Before publishing, revoke any key ever pasted into a tracked/example file. This project previously contained a Resend key in an example; removing a value does not revoke it. Confirm replacement in Resend and update your private configuration.
3. Review `git status --short`. `.env`, `data/`, databases, virtual environments, dependencies and Docker volumes must stay untracked. Review files before staging. Do not use force push.
4. Configure Git identity if needed. From the project root, after reviewing files:

```sh
git add .
git diff --cached --stat
git commit -m "Initial Margin workspace"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/margin.git
git push -u origin main
```

Replace the example URL with the exact repository URL. If a remote already exists, inspect it first rather than adding another one. Authenticate with GitHub's supported browser/credential flow or SSH; never put tokens in the remote URL or commands.

5. Check the CI workflow. Keep scheduled discovery disabled until remote storage is validated. Add a description, repository topics and a screenshot after reviewing it for personal data. The project includes an MIT license, contribution guide and security policy; enable private vulnerability reporting before public release.

Reference: [Adding locally hosted code to GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).
