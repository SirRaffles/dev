#!/bin/bash
# Backup the whisper transcription SQLite database.
# Designed to run via launchd timer (daily).

DB_PATH="$HOME/.whisper_transcription_jobs.db"
BACKUP_DIR="$HOME/.whisper-backups"
KEEP_DAYS=7

if [ ! -f "$DB_PATH" ]; then
    echo "Database not found: $DB_PATH"
    exit 0
fi

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/jobs_$TIMESTAMP.db"

# Use SQLite .backup command for a safe online backup
sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"

if [ $? -eq 0 ]; then
    echo "Backup created: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
else
    echo "Backup failed!"
    exit 1
fi

# Prune old backups
find "$BACKUP_DIR" -name "jobs_*.db" -mtime +$KEEP_DAYS -delete 2>/dev/null
REMAINING=$(ls -1 "$BACKUP_DIR"/jobs_*.db 2>/dev/null | wc -l)
echo "Backups retained: $REMAINING"
