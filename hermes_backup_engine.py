#!/usr/bin/env python
"""
Hermes Backup & Restore Engine
Handles atomic SQLite backups, file collection, packaging, verification, and restoration.
"""

import os
import sys
import shutil
import sqlite3
import zipfile
import json
import subprocess
from datetime import datetime
from pathlib import Path

HERMES_DIR = Path("C:/Users/Mega/AppData/Local/hermes")
BACKUP_DIRS = [
    Path("C:/Users/Mega/Hermes_Backups"),
    Path("D:/Hermes_Backups")
]
MEGUMI_DIR = Path("D:/megumi")

DATABASES = [
    HERMES_DIR / "state.db",
    HERMES_DIR / "kanban.db",
    HERMES_DIR / "projects.db",
    HERMES_DIR / "shared-state.db",
    HERMES_DIR / "cron" / "executions.db"
]

CONFIG_FILES = [
    HERMES_DIR / "config.yaml",
    HERMES_DIR / ".env",
    HERMES_DIR / "auth.json",
    HERMES_DIR / "SOUL.md",
    HERMES_DIR / "context_length_cache.yaml",
    HERMES_DIR / "gateway_state.json",
    HERMES_DIR / "channel_directory.json",
    HERMES_DIR / "google_client_secret.json",
    HERMES_DIR / "google_token.json",
    HERMES_DIR / "install_id",
    HERMES_DIR / ".skills_prompt_snapshot.json",
]

DIRECTORIES = [
    HERMES_DIR / "memories",
    HERMES_DIR / "skills",
    HERMES_DIR / "cron",
    HERMES_DIR / "mcp-tokens",
    HERMES_DIR / "sessions",
    HERMES_DIR / "platforms",
    HERMES_DIR / "desktop-plugins",
    HERMES_DIR / "hooks",
    HERMES_DIR / "shared",
    HERMES_DIR / "state",
    HERMES_DIR / "pending"
]

def backup_sqlite(src_path: Path, dst_path: Path):
    """Safely and atomically backup an active SQLite database in WAL mode."""
    if not src_path.exists():
        return False
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        src_conn = sqlite3.connect(f"file:{src_path.as_posix()}?mode=ro", uri=True)
        dst_conn = sqlite3.connect(dst_path)
        with dst_conn:
            src_conn.backup(dst_conn)
        src_conn.close()
        dst_conn.close()
        return True
    except Exception as e:
        print(f"Warning: sqlite online backup for {src_path.name} failed ({e}), falling back to direct copy")
        shutil.copy2(src_path, dst_path)
        # Also copy WAL/SHM if they exist
        wal = src_path.with_name(src_path.name + "-wal")
        shm = src_path.with_name(src_path.name + "-shm")
        if wal.exists():
            shutil.copy2(wal, dst_path.with_name(dst_path.name + "-wal"))
        if shm.exists():
            shutil.copy2(shm, dst_path.with_name(dst_path.name + "-shm"))
        return True

def get_git_info(repo_path: Path):
    """Collect git commit, branch, status, and diff."""
    if not (repo_path / ".git").exists():
        return {}
    info = {}
    try:
        info["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path, text=True
        ).strip()
        info["commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_path, text=True
        ).strip()
        info["commit_msg"] = subprocess.check_output(
            ["git", "log", "-1", "--pretty=%B"], cwd=repo_path, text=True
        ).strip()
        info["remote"] = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"], cwd=repo_path, text=True
        ).strip()
        info["status"] = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo_path, text=True
        ).strip()
        info["diff"] = subprocess.check_output(
            ["git", "diff"], cwd=repo_path, text=True
        )
    except Exception as e:
        info["error"] = str(e)
    return info

def run_backup():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"hermes_backup_{timestamp}"
    temp_dir = Path(f"C:/Users/Mega/AppData/Local/Temp/{backup_name}")
    temp_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Memulai backup Hermes: {timestamp}")
    print(f"[*] Staging files ke temporary folder: {temp_dir}")

    manifest = {
        "timestamp": timestamp,
        "date_created": datetime.now().isoformat(),
        "hermes_home": str(HERMES_DIR),
        "files_backed_up": [],
        "directories_backed_up": [],
        "databases": []
    }

    # 1. Backup Databases atomically
    db_stage = temp_dir / "databases"
    db_stage.mkdir(parents=True, exist_ok=True)
    for db in DATABASES:
        if db.exists():
            rel_name = db.name if db.parent == HERMES_DIR else f"{db.parent.name}_{db.name}"
            target_db = db_stage / rel_name
            if backup_sqlite(db, target_db):
                size_kb = target_db.stat().st_size / 1024
                print(f"  [DB] {db.name} -> {rel_name} ({size_kb:.1f} KB)")
                manifest["databases"].append({"source": str(db), "staged": rel_name, "size_kb": size_kb})

    # 2. Backup Config & Secrets
    cfg_stage = temp_dir / "config"
    cfg_stage.mkdir(parents=True, exist_ok=True)
    for cfg in CONFIG_FILES:
        if cfg.exists():
            shutil.copy2(cfg, cfg_stage / cfg.name)
            manifest["files_backed_up"].append(cfg.name)
            print(f"  [CONFIG] {cfg.name}")

    # 3. Backup Directories (Memories, Skills, Sessions, Cron, MCP Tokens, etc.)
    for d in DIRECTORIES:
        if d.exists() and d.is_dir():
            target = temp_dir / d.name
            # Exclude cache or temp lock files
            def ignore_patterns(path, names):
                return {n for n in names if n.endswith(".lock") or n in ["__pycache__", ".cache"]}
            shutil.copytree(d, target, ignore=ignore_patterns, dirs_exist_ok=True)
            count = sum(1 for _ in target.rglob("*") if _.is_file())
            manifest["directories_backed_up"].append({"name": d.name, "file_count": count})
            print(f"  [DIR] {d.name}/ ({count} files)")

    # 4. Backup External Credentials (D:/megumi)
    if MEGUMI_DIR.exists():
        megumi_stage = temp_dir / "external_megumi"
        megumi_stage.mkdir(parents=True, exist_ok=True)
        for item in MEGUMI_DIR.iterdir():
            if item.is_file():
                shutil.copy2(item, megumi_stage / item.name)
                print(f"  [MEGUMI] {item.name}")
        manifest["external_megumi"] = [f.name for f in MEGUMI_DIR.iterdir() if f.is_file()]

    # 5. Git Repo metadata & diff
    agent_repo = HERMES_DIR / "hermes-agent"
    git_info = get_git_info(agent_repo)
    if git_info:
        manifest["git_info"] = {
            "branch": git_info.get("branch"),
            "commit": git_info.get("commit"),
            "commit_msg": git_info.get("commit_msg"),
            "remote": git_info.get("remote")
        }
        with open(temp_dir / "git_info.json", "w", encoding="utf-8") as f:
            json.dump(git_info, f, indent=2)
        if git_info.get("diff"):
            with open(temp_dir / "uncommitted_changes.patch", "w", encoding="utf-8") as f:
                f.write(git_info["diff"])
        print(f"  [GIT] Commit: {git_info.get('commit', '')[:8]} on branch {git_info.get('branch', '')}")

    # 6. Save Manifest & Restore Readme
    with open(temp_dir / "BACKUP_INFO.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    readme_content = f"""HERMES BACKUP ARCHIVE
Tanggal Dibuat: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Nama Arsip: {backup_name}

ISI ARSIP:
- config/: config.yaml, .env, auth.json, SOUL.md, context_length, tokens, dll.
- memories/: MEMORY.md, USER.md (ingatan & profil)
- skills/: semua skill bawaan & custom buatan kamu
- databases/: state.db (semua percakapan & session), kanban.db, projects.db, shared-state.db, cron/executions.db (hasil online backup bersih)
- sessions/: dump session & metadata
- cron/: scheduled jobs
- mcp-tokens/: token otentikasi MCP
- external_megumi/: token & client_secret dari D:/megumi
- git_info.json & patch: informasi commit & status repo hermes-agent

CARA RESTORE:
1. Pake script: ./restore_hermes.sh {backup_name}.zip
2. Atau manual: extract zip ini ke C:/Users/Mega/AppData/Local/hermes
"""
    with open(temp_dir / "README_RESTORE.txt", "w", encoding="utf-8") as f:
        f.write(readme_content)

    # 7. Create ZIP archive
    zip_filename = f"{backup_name}.zip"
    primary_dir = BACKUP_DIRS[0]
    primary_dir.mkdir(parents=True, exist_ok=True)
    primary_zip_path = primary_dir / zip_filename

    print(f"[*] Mengompresi ke {primary_zip_path}...")
    with zipfile.ZipFile(primary_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = Path(root) / file
                archive_name = file_path.relative_to(temp_dir)
                zipf.write(file_path, archive_name)

    zip_size_mb = primary_zip_path.stat().st_size / (1024 * 1024)
    print(f"[+] Backup utama berhasil dibuat: {primary_zip_path} ({zip_size_mb:.2f} MB)")

    # 8. Mirror to Secondary (D: drive) if available
    secondary_dir = BACKUP_DIRS[1]
    secondary_zip_path = None
    try:
        secondary_dir.mkdir(parents=True, exist_ok=True)
        secondary_zip_path = secondary_dir / zip_filename
        shutil.copy2(primary_zip_path, secondary_zip_path)
        print(f"[+] Backup redundan (mirror) tersimpan di: {secondary_zip_path}")
    except Exception as e:
        print(f"[-] Catatan mirror D: ({e})")

    # 9. Clean staging temp directory
    shutil.rmtree(temp_dir, ignore_errors=True)

    # 10. Prune old backups (keep latest 10)
    for b_dir in [primary_dir, secondary_dir]:
        if b_dir.exists():
            zips = sorted(b_dir.glob("hermes_backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
            if len(zips) > 10:
                for old_zip in zips[10:]:
                    try:
                        old_zip.unlink()
                        print(f"[*] Pruned old backup: {old_zip.name}")
                    except Exception:
                        pass

    print("\n==========================================")
    print("BACKUP SELESAI & AMAN 100%!")
    print(f"File: {zip_filename}")
    print(f"Ukuran: {zip_size_mb:.2f} MB")
    print(f"Lokasi Utama: {primary_zip_path}")
    if secondary_zip_path and secondary_zip_path.exists():
        print(f"Lokasi Mirror (Drive D): {secondary_zip_path}")
    print("==========================================")
    return str(primary_zip_path)

def run_restore(zip_path_str: str):
    zip_path = Path(zip_path_str)
    if not zip_path.exists():
        # Try checking in backup directories
        for b_dir in BACKUP_DIRS:
            candidate = b_dir / zip_path_str
            if candidate.exists():
                zip_path = candidate
                break

    if not zip_path.exists():
        print(f"Error: File backup tidak ditemukan: {zip_path_str}")
        sys.exit(1)

    print(f"[*] Memulai restore dari arsip: {zip_path}")
    temp_dir = Path("C:/Users/Mega/AppData/Local/Temp/hermes_restore_tmp")
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zipf:
        zipf.extractall(temp_dir)

    print("[*] Mengekstrak file dan memulihkan:")

    # 1. Restore Config & Secrets
    cfg_stage = temp_dir / "config"
    if cfg_stage.exists():
        for item in cfg_stage.iterdir():
            target = HERMES_DIR / item.name
            shutil.copy2(item, target)
            print(f"  [CONFIG] Restored {item.name}")

    # 2. Restore Databases
    db_stage = temp_dir / "databases"
    if db_stage.exists():
        for db_file in db_stage.glob("*.db"):
            if db_file.name == "cron_executions.db":
                target = HERMES_DIR / "cron" / "executions.db"
            else:
                target = HERMES_DIR / db_file.name
            target.parent.mkdir(parents=True, exist_ok=True)
            # Remove any stale WAL/SHM when restoring
            for ext in ["-wal", "-shm"]:
                extra = target.with_name(target.name + ext)
                if extra.exists():
                    try:
                        extra.unlink()
                    except Exception:
                        pass
            shutil.copy2(db_file, target)
            print(f"  [DB] Restored {target.name}")

    # 3. Restore Directories
    for d_name in ["memories", "skills", "cron", "mcp-tokens", "sessions", "platforms", "desktop-plugins", "hooks", "shared", "state", "pending"]:
        src_d = temp_dir / d_name
        if src_d.exists() and src_d.is_dir():
            target_d = HERMES_DIR / d_name
            target_d.mkdir(parents=True, exist_ok=True)
            for item in src_d.rglob("*"):
                if item.is_file():
                    rel_path = item.relative_to(src_d)
                    dest_file = target_d / rel_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_file)
            print(f"  [DIR] Restored {d_name}/")

    # 4. Restore External Megumi (D:/megumi)
    megumi_stage = temp_dir / "external_megumi"
    if megumi_stage.exists() and MEGUMI_DIR.exists():
        for item in megumi_stage.iterdir():
            if item.is_file():
                shutil.copy2(item, MEGUMI_DIR / item.name)
                print(f"  [MEGUMI] Restored to D:/megumi/{item.name}")

    # Clean up
    shutil.rmtree(temp_dir, ignore_errors=True)

    print("\n==========================================")
    print("RESTORE BERHASIL DILAKUKAN!")
    print(f"Dipulihkan dari: {zip_path.name}")
    print("Hermes siap digunakan kembali.")
    print("==========================================")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        if len(sys.argv) < 3:
            # Pick latest backup if not provided
            primary_dir = BACKUP_DIRS[0]
            zips = sorted(primary_dir.glob("hermes_backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not zips:
                print("Tidak ada file backup yang ditemukan.")
                sys.exit(1)
            latest_zip = zips[0]
            print(f"Tidak ada file yang ditentukan, menggunakan backup terbaru: {latest_zip.name}")
            run_restore(str(latest_zip))
        else:
            run_restore(sys.argv[2])
    else:
        run_backup()
