-- rf_detections
--
-- SQLite translation of the PostgreSQL schema sir provided. Run this
-- from the sqlite3 shell (or "python manage.py dbshell") with:
--
--     sqlite> .read create_table.sql
--
-- Type mapping notes (Postgres -> SQLite):
--   integer               -> INTEGER
--   uuid                  -> TEXT            (36-char uuid string)
--   double precision      -> REAL
--   boolean                -> INTEGER         (0 = false, 1 = true)
--   character varying(n)   -> TEXT            (SQLite ignores the length)
--   timestamp without tz   -> TEXT            ("YYYY-MM-DD HH:MM:SS")
--   serial / identity PK    -> INTEGER PRIMARY KEY  (auto-increments)
--
-- "range" is a plain column name here, not a SQL keyword in SQLite,
-- but it is quoted everywhere it is used just to be safe.

CREATE TABLE IF NOT EXISTS rf_detections (
    rf_detection_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    modality_id                 INTEGER NOT NULL,
    site_id                      TEXT NOT NULL,
    sdr_detection_param_id       INTEGER NOT NULL,
    sdr_localization_param_id    INTEGER NOT NULL,
    detected_3db_bw               REAL NOT NULL,
    detected_10db_bw               REAL NOT NULL,
    ml_detection_status             INTEGER NOT NULL,
    ml_confidence                    REAL NOT NULL,
    azimuth                          REAL NOT NULL,
    elevation                        REAL NOT NULL,
    antenna_id                       INTEGER NOT NULL,
    signal_type                      TEXT,
    rssi                             REAL,
    "range"                          REAL,
    spectrum_path                    TEXT,
    center_frequency                  REAL DEFAULT 2400,
    _is_active                        INTEGER DEFAULT 1,
    _last_update_time                  TEXT DEFAULT (datetime('now')),
    _last_update_user                  INTEGER NOT NULL,
    _last_update_remarks                TEXT,
    tolerance                           REAL DEFAULT 5,
    drone_id                            INTEGER
);

-- The dashboard filters/sorts by time and only looks at active rows,
-- so both are worth an index once the table has real volume.
CREATE INDEX IF NOT EXISTS idx_rf_detections_last_update_time
    ON rf_detections(_last_update_time);

CREATE INDEX IF NOT EXISTS idx_rf_detections_is_active
    ON rf_detections(_is_active);
