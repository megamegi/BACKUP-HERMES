#!/usr/bin/env bash
# ==============================================================================
# Hermes & Megumi Restore Script for Git Bash
# ==============================================================================
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================${NC}"
echo -e "${YELLOW}       PERINGATAN: RESTORE BACKUP HERMES & MEGUMI      ${NC}"
echo -e "${BLUE}======================================================${NC}"

# Find python
if command -v python &> /dev/null; then
    PY_BIN="python"
elif [ -f "C:/Users/Mega/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" ]; then
    PY_BIN="C:/Users/Mega/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
else
    echo -e "${RED}Python tidak ditemukan di PATH!${NC}"
    exit 1
fi

TARGET_FILE="$1"

if [ -z "$TARGET_FILE" ]; then
    echo -e "${YELLOW}Tidak ada file backup yang dipilih secara spesifik.${NC}"
    echo -e "Script akan otomatis memulihkan dari backup TERBARU."
    echo -e "Lanjutkan? (Tekan Ctrl+C untuk batal, atau Enter untuk lanjut)"
    read -r
    "$PY_BIN" "C:/Users/Mega/hermes_backup_engine.py" restore
else
    echo -e "Memulihkan dari file: ${GREEN}$TARGET_FILE${NC}"
    "$PY_BIN" "C:/Users/Mega/hermes_backup_engine.py" restore "$TARGET_FILE"
fi

echo -e "\n${GREEN}Restore berhasil diselesaikan!${NC}"
