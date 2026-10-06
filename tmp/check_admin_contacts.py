import sqlite3
from pathlib import Path

for file in (Path('db.sqlite3'), Path('codex-test.sqlite3')):
    if not file.exists():
        continue
    db = sqlite3.connect(f'file:{file.resolve().as_posix()}?mode=ro', uri=True)
    print('LOCAL DATABASE:', file)
    tables = {row[0] for row in db.execute('SELECT name FROM sqlite_master WHERE type = ?', ('table',))}
    if {'auth_user', 'core_useraccess'} <= tables:
        cols = {row[1] for row in db.execute('PRAGMA table_info(core_useraccess)')}
        if 'role' in cols:
            print('Administrative profiles:', db.execute('SELECT u.username, u.email, a.role FROM auth_user u JOIN core_useraccess a ON a.user_id=u.id WHERE a.role IN (?, ?)', ('admin', 'collaborator')).fetchall())
    if 'core_contactomanager' in tables:
        print('Staff contacts:', db.execute('SELECT manager, email, actualizado FROM core_contactomanager WHERE lower(manager) IN (?, ?, ?, ?, ?)', ("kabe's team", 'kabes team', 'llull team', 'reventao', 'pablo cuevas')).fetchall())
    db.close()
