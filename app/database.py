import sqlite3
from contextlib import contextmanager
from app.config import settings

@contextmanager
def get_db():
    conn = sqlite3.connect(settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                email_verified INTEGER DEFAULT 0,
                verification_code_hash TEXT,
                verification_expires TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Notes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                label TEXT,
                patient_age TEXT,
                patient_gender TEXT,
                visit_type TEXT,
                specialty TEXT,
                chief_complaint TEXT,
                raw_dictation TEXT,
                soap_note TEXT,
                encounter_time TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        ''')
        
        # Add encounter_time column if it doesn't exist (migration for existing tables)
        try:
            cursor.execute('ALTER TABLE notes ADD COLUMN encounter_time TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        
        conn.commit()
