from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import threading
import uuid

from .schemas import MonitorSettings, Zone, ZoneInput


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class ConflictError(Exception):
    pass


class Store:
    def __init__(self, settings, class_names):
        self.settings = settings
        self.directory = settings.data_dir
        self.directory.mkdir(parents=True, exist_ok=True)
        self.uploads = self.directory / "uploads"
        self.snapshots = self.directory / "snapshots"
        self.uploads.mkdir(exist_ok=True)
        self.snapshots.mkdir(exist_ok=True)
        self.path = self.directory / "safety.sqlite3"
        self.lock = threading.RLock()
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS zones (id TEXT PRIMARY KEY, source_id TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS zones_source ON zones(source_id);
                CREATE TABLE IF NOT EXISTS videos (id TEXT PRIMARY KEY, name TEXT NOT NULL, filename TEXT NOT NULL, size INTEGER NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY, source_id TEXT NOT NULL, zone_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, payload TEXT NOT NULL, snapshot TEXT,
                    acknowledged_at TEXT, resolved_at TEXT
                );
                CREATE INDEX IF NOT EXISTS alerts_time ON alerts(created_at DESC);
                PRAGMA user_version=1;
            """)
            schema = json.dumps(class_names, sort_keys=True)
            old = db.execute("SELECT value FROM meta WHERE key='class_schema'").fetchone()
            if old and old[0] != schema:
                raise ValueError("Stored zone class schema differs from this model; migrate zones before changing class order")
            db.execute("INSERT OR REPLACE INTO meta VALUES ('class_schema', ?)", (schema,))

    @contextmanager
    def connection(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=5)
            db.row_factory = sqlite3.Row
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    def zones(self, source_id):
        with self.connection() as db:
            rows = db.execute("SELECT payload FROM zones WHERE source_id=? ORDER BY rowid", (source_id,)).fetchall()
        return [Zone.model_validate_json(row[0]) for row in rows]

    def zone(self, zone_id):
        with self.connection() as db:
            row = db.execute("SELECT payload FROM zones WHERE id=?", (zone_id,)).fetchone()
        if not row:
            raise KeyError(zone_id)
        return Zone.model_validate_json(row[0])

    def create_zone(self, value: ZoneInput):
        zone = Zone(**value.model_dump(), id=uuid.uuid4().hex, updated_at=utc_now())
        with self.connection() as db:
            count = db.execute("SELECT COUNT(*) FROM zones WHERE source_id=?", (zone.source_id,)).fetchone()[0]
            if count >= self.settings.max_zones:
                raise ValueError(f"A source can have at most {self.settings.max_zones} zones")
            db.execute("INSERT INTO zones VALUES (?,?,?)", (zone.id, zone.source_id, zone.model_dump_json()))
        return zone

    def update_zone(self, value: ZoneInput, zone_id, expected_version):
        with self.connection() as db:
            old = self.zone(zone_id)
            if expected_version is not None and expected_version != old.version:
                raise ConflictError("This zone was changed in another session. Reload and try again.")
            zone = Zone(**value.model_dump(), id=old.id, version=old.version + 1, updated_at=utc_now())
            db.execute("UPDATE zones SET payload=? WHERE id=?", (zone.model_dump_json(), zone_id))
        return zone

    def delete_zone(self, zone_id):
        with self.connection() as db:
            if not db.execute("DELETE FROM zones WHERE id=?", (zone_id,)).rowcount:
                raise KeyError(zone_id)

    def monitor_settings(self):
        with self.connection() as db:
            row = db.execute("SELECT value FROM meta WHERE key='monitor_settings'").fetchone()
        return MonitorSettings.model_validate_json(row[0]) if row else MonitorSettings()

    def save_settings(self, value):
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO meta VALUES ('monitor_settings',?)", (value.model_dump_json(),))

    def videos(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM videos ORDER BY created_at DESC")]

    def add_video(self, video_id, name, filename, size):
        with self.connection() as db:
            db.execute("INSERT INTO videos VALUES (?,?,?,?,?)", (video_id, name, filename, size, utc_now()))

    def add_alert(self, payload, snapshot):
        alert_id = uuid.uuid4().hex
        with self.connection() as db:
            db.execute("INSERT INTO alerts VALUES (?,?,?,?,?,?,NULL,NULL)",
                       (alert_id, payload["source_id"], payload["zone_id"], utc_now(), json.dumps(payload), snapshot))
        return alert_id

    @staticmethod
    def public_alert(row):
        return {**json.loads(row["payload"]), "id": row["id"], "created_at": row["created_at"],
                "acknowledged_at": row["acknowledged_at"], "resolved_at": row["resolved_at"],
                "snapshot_url": f"/api/alerts/{row['id']}/snapshot" if row["snapshot"] else None}

    def alerts(self, limit=50, offset=0, kind=None, acknowledged=None):
        where, args = [], []
        if kind:
            where.append("json_extract(payload,'$.kind')=?")
            args.append(kind)
        if acknowledged is not None:
            where.append("acknowledged_at IS NOT NULL" if acknowledged else "acknowledged_at IS NULL")
        clause = " WHERE " + " AND ".join(where) if where else ""
        with self.connection() as db:
            total = db.execute("SELECT COUNT(*) FROM alerts" + clause, args).fetchone()[0]
            rows = db.execute("SELECT * FROM alerts" + clause + " ORDER BY created_at DESC LIMIT ? OFFSET ?", (*args, limit, offset)).fetchall()
        return {"items": [self.public_alert(row) for row in rows], "total": total, "limit": limit, "offset": offset}

    def acknowledge(self, alert_id):
        with self.connection() as db:
            if not db.execute("UPDATE alerts SET acknowledged_at=COALESCE(acknowledged_at,?) WHERE id=?", (utc_now(), alert_id)).rowcount:
                raise KeyError(alert_id)

    def resolve(self, alert_id, reason="not_observed"):
        with self.connection() as db:
            db.execute("UPDATE alerts SET resolved_at=COALESCE(resolved_at,?), payload=json_set(payload,'$.resolution_reason',?) WHERE id=?", (utc_now(), reason, alert_id))

    def close_interrupted_alerts(self):
        with self.connection() as db:
            db.execute("UPDATE alerts SET resolved_at=?, payload=json_set(payload,'$.resolution_reason','monitoring_restarted') WHERE resolved_at IS NULL", (utc_now(),))

    def snapshot_path(self, alert_id):
        with self.connection() as db:
            row = db.execute("SELECT snapshot FROM alerts WHERE id=?", (alert_id,)).fetchone()
        if not row or not row[0]:
            raise KeyError(alert_id)
        path = (self.snapshots / row[0]).resolve()
        if not path.is_relative_to(self.snapshots.resolve()) or not path.is_file():
            raise KeyError(alert_id)
        return path

    def prune(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.settings.retention_days)).isoformat()
        with self.connection() as db:
            rows = db.execute("""SELECT id,snapshot FROM alerts WHERE created_at<? OR id IN
                (SELECT id FROM alerts ORDER BY created_at DESC LIMIT -1 OFFSET ?)""", (cutoff, self.settings.max_alerts)).fetchall()
            candidates = {row["snapshot"] for row in rows if row["snapshot"]}
            db.executemany("DELETE FROM alerts WHERE id=?", [(row["id"],) for row in rows])
            for filename in candidates:
                if not db.execute("SELECT 1 FROM alerts WHERE snapshot=? LIMIT 1", (filename,)).fetchone():
                    path = (self.snapshots / filename).resolve()
                    if path.is_relative_to(self.snapshots.resolve()):
                        path.unlink(missing_ok=True)
