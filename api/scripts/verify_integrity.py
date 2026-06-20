import sqlite3
import logging
from pathlib import Path

DB_PATH = Path("/data/db/joidy.db")
logger = logging.getLogger(__name__)

def check_integrity():
    if not DB_PATH.exists():
        logger.error("Database not found at %s", DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    logger.info("--- Auditoria de Integridad de Joidy ---")

    # 1. Check orphaned note_links
    cursor.execute("""
        SELECT COUNT(*) FROM note_links 
        WHERE source_note_id NOT IN (SELECT id FROM notes)
        OR target_note_id NOT IN (SELECT id FROM notes)
    """)
    orphaned_links = cursor.fetchone()[0]
    logger.info("[Links] Enlaces huerfanos detectados: %s", orphaned_links)

    # 2. Check orphaned skills
    cursor.execute("""
        SELECT COUNT(*) FROM skills 
        WHERE tag_id NOT IN (SELECT id FROM tags)
    """)
    orphaned_skills = cursor.fetchone()[0]
    logger.info("[Skills] Habilidades huerfanas detectadas: %s", orphaned_skills)

    # 3. Check orphaned note_tags
    cursor.execute("""
        SELECT COUNT(*) FROM note_tags 
        WHERE note_id NOT IN (SELECT id FROM notes)
        OR tag_id NOT IN (SELECT id FROM tags)
    """)
    orphaned_tags = cursor.fetchone()[0]
    logger.info("[Tags] Tags de notas huerfanos detectados: %s", orphaned_tags)

    # 4. Check for notes without source_path (Obsidian notes only)
    cursor.execute("SELECT COUNT(*) FROM notes WHERE source = 'obsidian' AND source_path IS NULL")
    missing_paths = cursor.fetchone()[0]
    logger.info("[Notes] Notas de Obsidian sin path de origen: %s", missing_paths)

    logger.info("--- Fin de la auditoria ---")
    conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    check_integrity()
