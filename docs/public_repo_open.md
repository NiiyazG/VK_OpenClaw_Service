# Public Repository Checklist (No Secrets)

Use this checklist to create a public clone of the project without secret data.

## 1) Create a clean repository snapshot
1. Copy project files to a new folder without `.git` history.
2. Ensure local runtime artifacts are excluded (`.venv*`, `state/`, build caches, temp folders).
3. Initialize a new git repository in the new folder.

## 2) Keep only safe config templates
- Keep `.env.example` with placeholders.
- Do not include real `.env`.
- Verify `.gitignore` includes `.env` and secret-like local files.

## 3) Scan before first commit
Run a quick scan for obvious secret patterns:
```bash
rg -n --hidden --glob '!.git/*' "(BEGIN .*PRIVATE KEY|ghp_|github_pat_|xoxb-|AKIA|VK_ACCESS_TOKEN=|ADMIN_API_TOKEN=)"
```

Then manually inspect results and ensure only template/sample values remain.

## 4) Publish to GitHub
1. Create a new empty GitHub repo.
2. Add remote in the new clean repo.
3. Push initial commit.

## 5) Security baseline for open-source
- Enable branch protection for `main`.
- Enable GitHub secret scanning and Dependabot alerts.
- Require PR review for protected branch.

## Author
- Гарипов Нияз Варисович
- garipovn@yandex.ru
