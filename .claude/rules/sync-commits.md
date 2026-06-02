# Sync Commits from Internal Repo

When syncing commits from the internal project (`~/projects/android-mcp-pro`) to this public repo:

1. Use `git format-patch` to export the specified commits
2. Apply with `git am --reset-author` so the author is rewritten to this project's identity (`Eddie <freewangei@gmail.com>`)
3. Verify no company info (xiaomi, wangwei114) appears in the rewritten commits

Example workflow:
```bash
# Sync last N commits from internal
cd ~/projects/android-mcp-pro
git format-patch -N --stdout | git -C ~/github-projects/android-mcp-pro am --reset-author

# Sync a specific range
git format-patch abc123..def456 --stdout | git -C ~/github-projects/android-mcp-pro am --reset-author
```

After applying, always run `git log --format='%an <%ae>' -N` to confirm author is correct.
