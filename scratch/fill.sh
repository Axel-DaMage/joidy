start_date="2025-12-02"
end_date=$(date -I)
current_date="$start_date"
streak_id=2

while [ "$current_date" != "$end_date" ]; do
    sqlite3 data/db/joidy.db "INSERT OR IGNORE INTO streak_checkins (streak_id, check_date, note) VALUES ($streak_id, '$current_date', 'Auto-generado (Migración)');"
    current_date=$(date -I -d "$current_date + 1 day")
done

# Update total_checkins count
count=$(sqlite3 data/db/joidy.db "SELECT COUNT(*) FROM streak_checkins WHERE streak_id=$streak_id;")
sqlite3 data/db/joidy.db "UPDATE personal_streaks SET total_checkins=$count WHERE id=$streak_id;"
