"""Local journal accounts and atomic drafts, independent of the application bundle."""
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import uuid

from werkzeug.security import check_password_hash, generate_password_hash


class RevisionConflict(Exception):
    """Another window saved a newer revision."""


class DuplicateUsername(ValueError):
    pass


def data_directory():
    override = os.environ.get('AIDITOR_DATA_DIR')
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'AI-ditor Plus'
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'AI-ditor Plus'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'aiditor-plus'


def check_id(value):
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Kayıt kimliği geçersiz.') from exc


def _encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True, allow_nan=False)


def _revision(value):
    if type(value) is not int or value < 0:
        raise ValueError('Kayıt sürümü geçersiz.')


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


class AccountStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else data_directory()

    def _connect(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.directory / 'aiditor.sqlite3'
        db = sqlite3.connect(path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            if os.name != 'nt':
                path.chmod(0o600)
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA synchronous=FULL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                    display_name TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS journals (
                    owner TEXT PRIMARY KEY REFERENCES accounts(id), settings TEXT NOT NULL,
                    assets TEXT NOT NULL, revision INTEGER NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS articles (
                    owner TEXT NOT NULL REFERENCES accounts(id), id TEXT NOT NULL, title TEXT NOT NULL,
                    authors TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL,
                    project TEXT NOT NULL, PRIMARY KEY(owner,id));
            ''')
            db.commit()
            return db
        except Exception:
            db.close()
            raise

    def session_secret(self):
        with closing(self._connect()) as db, db:
            db.execute('INSERT OR IGNORE INTO app_meta VALUES (?,?)', ('session_secret', secrets.token_hex(48)))
            return db.execute('SELECT value FROM app_meta WHERE key=?', ('session_secret',)).fetchone()['value']

    def register(self, username, display_name, password, settings):
        owner = str(uuid.uuid4())
        password_hash = generate_password_hash(password, method='scrypt')
        now = _now()
        try:
            with closing(self._connect()) as db, db:
                db.execute('INSERT INTO accounts VALUES (?,?,?,?,?)', (owner, username, display_name, password_hash, now))
                db.execute('INSERT INTO journals VALUES (?,?,?,?,?)', (owner, _encode(settings), '{}', 0, now))
        except sqlite3.IntegrityError as exc:
            raise DuplicateUsername('Bu kullanıcı adı zaten kullanılıyor.') from exc
        return dict(id=owner, username=username, display_name=display_name)

    def user(self, owner):
        with closing(self._connect()) as db:
            row = db.execute('SELECT id,username,display_name FROM accounts WHERE id=?', (owner,)).fetchone()
            return dict(row) if row else None

    def authenticate(self, username, password):
        with closing(self._connect()) as db:
            row = db.execute('SELECT * FROM accounts WHERE username=?', (username,)).fetchone()
        # A fixed dummy hash keeps absent usernames on the same slow password path.
        password_hash = row['password_hash'] if row else self._dummy_hash()
        valid = check_password_hash(password_hash, password)
        return dict(id=row['id'], username=row['username'], display_name=row['display_name']) if row and valid else None

    @staticmethod
    def _dummy_hash():
        return 'scrypt:32768:8:1$aiditorDummySalt$' + '0' * 128

    def journal(self, owner):
        with closing(self._connect()) as db:
            row = db.execute('SELECT * FROM journals WHERE owner=?', (owner,)).fetchone()
            if row is None:
                return None
            return dict(settings=json.loads(row['settings']), assets=json.loads(row['assets']), revision=row['revision'], updated_at=row['updated_at'])

    def save_journal(self, owner, settings, assets_patch, base_revision):
        _revision(base_revision)
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM journals WHERE owner=?', (owner,)).fetchone()
            if row is None:
                raise ValueError('Dergi hesabı bulunamadı.')
            assets = json.loads(row['assets'])
            assets.update(assets_patch)
            assets = {key: value for key, value in assets.items() if value is not None}
            encoded_settings, encoded_assets = _encode(settings), _encode(assets)
            if row['settings'] == encoded_settings and row['assets'] == encoded_assets:
                return dict(settings=settings, assets=assets, revision=row['revision'], updated_at=row['updated_at'])
            if row['revision'] != base_revision:
                raise RevisionConflict
            revision, now = row['revision'] + 1, _now()
            db.execute('UPDATE journals SET settings=?,assets=?,revision=?,updated_at=? WHERE owner=?',
                       (encoded_settings, encoded_assets, revision, now, owner))
            return dict(settings=settings, assets=assets, revision=revision, updated_at=now)

    def articles(self, owner):
        with closing(self._connect()) as db:
            return [dict(row) for row in db.execute('SELECT id,title,authors,updated_at,revision FROM articles WHERE owner=? ORDER BY updated_at DESC,id', (owner,))]

    def article(self, owner, article_id):
        check_id(article_id)
        with closing(self._connect()) as db:
            row = db.execute('SELECT id,title,authors,updated_at,revision,project FROM articles WHERE owner=? AND id=?', (owner, article_id)).fetchone()
            if row is None:
                return None
            result = dict(row)
            result['project'] = json.loads(result['project'])
            return result

    def save_article(self, owner, article_id, project, base_revision):
        check_id(article_id)
        _revision(base_revision)
        encoded = _encode(project)
        data = project['data']
        title = (data['cover'].get('tr_title', '').strip() or data['cover'].get('en_title', '').strip() or 'Başlıksız makale')[:500]
        authors = ', '.join(author.get('name', '').strip() for author in data['authors'] if author.get('name', '').strip())[:1000]
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT revision,project,updated_at FROM articles WHERE owner=? AND id=?', (owner, article_id)).fetchone()
            revision = row['revision'] if row else 0
            if row and row['project'] == encoded:
                return dict(id=article_id, title=title, authors=authors, updated_at=row['updated_at'], revision=revision)
            if revision != base_revision:
                raise RevisionConflict
            now = _now()
            db.execute('''INSERT INTO articles VALUES (?,?,?,?,?,?,?) ON CONFLICT(owner,id) DO UPDATE SET
                title=excluded.title,authors=excluded.authors,updated_at=excluded.updated_at,
                revision=excluded.revision,project=excluded.project''',
                       (owner, article_id, title, authors, now, revision + 1, encoded))
            return dict(id=article_id, title=title, authors=authors, updated_at=now, revision=revision + 1)

    def delete_article(self, owner, article_id, base_revision):
        check_id(article_id)
        _revision(base_revision)
        with closing(self._connect()) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT revision FROM articles WHERE owner=? AND id=?', (owner, article_id)).fetchone()
            if row is None:
                return False
            if row['revision'] != base_revision:
                raise RevisionConflict
            db.execute('DELETE FROM articles WHERE owner=? AND id=?', (owner, article_id))
            return True
