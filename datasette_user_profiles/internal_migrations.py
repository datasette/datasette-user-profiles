from sqlite_utils import Database
from sqlite_migrate import Migrations

internal_migrations = Migrations("datasette-user-profiles.internal")


@internal_migrations()
def m001_initial(db: Database):
    db.executescript("""
        CREATE TABLE datasette_user_profiles (
            actor_id TEXT PRIMARY KEY,
            display_name TEXT,
            bio TEXT,
            email TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
        );

        CREATE TABLE datasette_user_profile_photos (
            actor_id TEXT PRIMARY KEY REFERENCES datasette_user_profiles(actor_id) ON DELETE CASCADE,
            photo BLOB NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'image/jpeg',
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
            CHECK (length(photo) <= 1048576)
        );
    """)


@internal_migrations()
def m002_avatar_icon_color(db: Database):
    db.executescript("""
        ALTER TABLE datasette_user_profiles ADD COLUMN avatar_icon TEXT;
        ALTER TABLE datasette_user_profiles ADD COLUMN avatar_color TEXT;
    """)
