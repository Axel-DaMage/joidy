import sqlite3
import os
from pathlib import Path

DB_PATH = Path("/data/db/joidy.db")

def check_integrity():
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- Auditoría de Integridad de Joidy ---")

    # 1. Check orphaned note_links
    cursor.execute("""
        SELECT COUNT(*) FROM note_links 
        WHERE source_note_id NOT IN (SELECT id FROM notes)
        OR target_note_id NOT IN (SELECT id FROM notes)
    """)
    orphaned_links = cursor.fetchone()[0]
    print(f"[Links] Enlaces huérfanos detectados: {orphaned_links}")

    # 2. Check orphaned skills
    cursor.execute("""
        SELECT COUNT(*) FROM skills 
        WHERE tag_id NOT IN (SELECT id FROM tags)
    """)
    orphaned_skills = cursor.fetchone()[0]
    print(f"[Skills] Habilidades huérfanas detectadas: {orphaned_skills}")

    # 3. Check orphaned note_tags
    cursor.execute("""
        SELECT COUNT(*) FROM note_tags 
        WHERE note_id NOT IN (SELECT id FROM notes)
        OR tag_id NOT IN (SELECT id FROM tags)
    """)
    orphaned_tags = cursor.fetchone()[0]
    print(f"[Tags] Tags de notas huérfanos detectados: {orphaned_tags}")

    # 4. Check for notes without source_path (Obsidian notes only)
    cursor.execute("SELECT COUNT(*) FROM notes WHERE source = 'obsidian' AND source_path IS NULL")
    missing_paths = cursor.fetchone()[0]
    print(f"[Notes] Notas de Obsidian sin path de origen: {missing_paths}")

    print("--- Fin de la auditoría ---")
    conn.close()

if __name__ == "__main__":
    check_integrity()
