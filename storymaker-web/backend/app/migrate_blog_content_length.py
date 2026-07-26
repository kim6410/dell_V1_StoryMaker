# -*- coding: utf-8 -*-
"""One-time safe migration for user_personas.blog_content_length."""
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

DB_PATH = Path('/home/bourne/StoryMaker_1/database/storymaker.db')


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f'DB not found: {DB_PATH}')
    backup_path = DB_PATH.with_name(DB_PATH.name + '.bak_blog_length_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(DB_PATH, backup_path)
    conn = sqlite3.connect(DB_PATH)
    try:
        cols = [row[1] for row in conn.execute('PRAGMA table_info(user_personas)').fetchall()]
        added = False
        if 'blog_content_length' not in cols:
            conn.execute('ALTER TABLE user_personas ADD COLUMN blog_content_length INTEGER NOT NULL DEFAULT 1500')
            added = True
        conn.execute('UPDATE user_personas SET blog_content_length = 1500 WHERE blog_content_length IS NULL OR blog_content_length NOT IN (1200, 1500, 2000)')
        conn.commit()
        cols_after = [row[1] for row in conn.execute('PRAGMA table_info(user_personas)').fetchall()]
        count = conn.execute('SELECT COUNT(*) FROM user_personas').fetchone()[0]
    finally:
        conn.close()
    print(f'backup={backup_path}')
    print(f'added={added}')
    print(f'has_blog_content_length={"blog_content_length" in cols_after}')
    print(f'user_personas_count={count}')


if __name__ == '__main__':
    main()
