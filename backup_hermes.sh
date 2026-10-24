#!/usr/bin/env bash
# ==============================================================================
# Hermes & Megumi Backup Script for Git Bash
# ==============================================================================
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================${NC}"
echo -e "${GREEN}       MEMULAI PROSES BACKUP LENGKAP HERMES & MEGUMI   ${NC}"
echo -e "${BLUE}======================================================${NC}"

# Find python
if command -v python &> /dev/null; then
    PY_BIN="python"
elif [ -f "C:/Users/Mega/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" ]; then
    PY_BIN="C:/Users/Mega/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
else
    echo -e "${YELLOW}Python tidak ditemukan di PATH!${NC}"
    exit 1
fi

"$PY_BIN" "C:/Users/Mega/hermes_backup_engine.py" backup

echo -e "\n${BLUE}Daftar 5 Backup Terbaru di C:/Users/Mega/Hermes_Backups:${NC}"
ls -lhrt "C:/Users/Mega/Hermes_Backups" | tail -n 5

if [ -d "D:/Hermes_Backups" ]; then
    echo -e "\n${BLUE}Daftar Mirror Backup di D:/Hermes_Backups:${NC}"
    ls -lhrt "D:/Hermes_Backups" | tail -n 5
fi

echo -e "\n${GREEN}Selesai! Kamu bisa restore kapan saja dengan:${NC}"
echo -e "  ${YELLOW}./restore_hermes.sh [nama_file.zip]${NC} atau jalankan tanpa argumen untuk restore yang terbaru."
