## File Storage System

This project uses a unified file storage abstraction for all user and chat/session data. By default, files are stored locally. If the `GIT_STORAGE` environment variable is set, all file access is transparently redirected to a remote git repository.

**How it works:**
- If `GIT_STORAGE` is set (format: `https://user:pwd@url-of-repo`), all file operations (read, write, remove, list) are performed in a cloned working tree of the specified git repository. Changes are committed and pushed automatically.
- If `GIT_STORAGE` is not set, files are stored and accessed locally as before.

**To enable git-backed storage:**
1. Set the `GIT_STORAGE` environment variable to your repo URL, e.g.:
   ```
   export GIT_STORAGE="https://username:password@git.example.com/your/repo.git"
   ```
2. Restart the application.

All file access in the codebase is routed through this abstraction, so no further code changes are needed to switch storage backends.

---
title: Nebenchat
emoji: 🐠
colorFrom: green
colorTo: yellow
sdk: docker
pinned: false
license: mit
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference

Gihub repo: https://github.com/dn-scribe/nebnechat
HF repo: https://huggingface.co/spaces/dn-9281411/nebenchat