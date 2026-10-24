---
name: state-backup-and-recovery
description: Use when backing up or restoring agent state and databases.
---

# State Backup and Recovery

Procedure and invariants for reliably backing up and restoring active AI agent state, persistent memory, SQLite databases in WAL mode, and secrets across environments.

## Invariants

- **Never copy active SQLite files directly**: When SQLite operates in WAL mode (`state.db`, `state.db-wal`, `state.db-shm`), a direct filesystem copy while the agent is running risks torn pages, database locking (`EBUSY` or `PermissionError` on Windows), or lost recent transactions.
- **Use SQLite online backup API**: Always use `sqlite3.connect(...).backup(...)` (or `VACUUM INTO`) via Python to obtain an atomic, transactionally consistent snapshot.
- **Exclude ephemeral caches and environments**: Never include virtual environments (`venv/`, `.venv/`), `node_modules/`, compiler artifacts, build releases, or heavy model weight caches in state backups. Keep archives compact (< 50 MB) so they can be replicated and mirrored quickly.
- **Multi-drive mirror**: When multiple physical drives or partitions are available, mirror the compressed archive to secondary storage for cross-drive redundancy.

## Backup Procedure

1. **Identify State Boundaries**:
   - Configuration & Secrets: `config.yaml`, `.env`, `auth.json`, `SOUL.md`, platform tokens, OAuth client secrets.
   - Databases: `state.db` (conversation history), `kanban.db`, `projects.db`, `shared-state.db`, `executions.db`.
   - Dynamic State Directories: `memories/`, `skills/`, `cron/`, `sessions/`, `mcp-tokens/`.
   - Repository Metadata: Git commit hash, current branch, and uncommitted patch (`git diff`).

2. **Atomic SQLite Online Backup**:
   Run via Python using read-only source connection:
   ```python
   import sqlite3
   src = sqlite3.connect(f"file:{src_db}?mode=ro", uri=True)
   dst = sqlite3.connect(dst_db)
   with dst:
       src.backup(dst)
   src.close()
   dst.close()
   ```

3. **Archive Packaging**:
   - Collect staged configs, databases, and state folders.
   - Exclude lock files (`*.lock`), bytecode caches (`__pycache__`), and temporary sockets.
   - Include a `BACKUP_INFO.json` manifest with timestamps, file counts, and hashes.
   - Compress to ZIP (for native Windows/Explorer extraction) or `tar.gz`.

4. **Retention Policy**:
   - Retain the latest N backups (e.g. 5–10) and prune older archives to prevent storage exhaustion.

## Restoration Procedure

1. Shut down any running gateway or background agent processes to release file locks.
2. Extract the archive into a staging directory.
3. Clean existing stale `-wal` and `-shm` files before copying restored `.db` files into place to prevent SQLite from applying orphaned WAL transactions.
4. Restore configuration, memories, and skills.
5. Restart services and verify agent health.
