import random
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DB_PATH = PROJECT_ROOT / 'db.sqlite3'
CREATE_TABLE_SQL_PATH = PROJECT_ROOT / 'create_table.sql'

SEED_TAG = 'dummy-seed'

random.seed(42)

BASE_DATE = date(2026, 6, 1)
TIMES = ['06:00', '09:00', '12:00', '15:00', '18:00', '21:00']
NUM_DAYS = 14
BEARING_STEP_DEG = 5

SIGNAL_TYPES = ['FHSS', 'OFDM', 'FSK', 'unknown']
SITE_IDS = [str(uuid.uuid4()) for _ in range(3)]  # a handful of fixed sensor sites


def ensure_table(conn):
    sql = CREATE_TABLE_SQL_PATH.read_text(encoding='ascii')
    conn.executescript(sql)


def clear_previous_seed(conn):
    conn.execute(
        "DELETE FROM rf_detections WHERE _last_update_remarks = ?",
        (SEED_TAG,),
    )


def build_rows():
    rows = []
    for d in range(NUM_DAYS):
        cur_date = BASE_DATE + timedelta(days=d)
        for t in TIMES:
            hour, minute = (int(p) for p in t.split(':'))
            timestamp = datetime(cur_date.year, cur_date.month, cur_date.day, hour, minute)
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')

            num_hotspots = random.randint(1, 3)
            hotspot_bearings = random.sample(range(0, 360, BEARING_STEP_DEG), num_hotspots)
            site_id = random.choice(SITE_IDS)

            for bearing in range(0, 360, BEARING_STEP_DEG):
                # base low confidence (mostly background noise / no drone)
                confidence = random.uniform(0.0, 0.35)

                for hb in hotspot_bearings:
                    diff = min(abs(bearing - hb), 360 - abs(bearing - hb))
                    if diff <= 20:
                        bump = (1 - diff / 20) * random.uniform(0.55, 1.0)
                        confidence = max(confidence, bump)
                confidence = round(min(confidence, 1.0), 4)

                range_km = round(random.uniform(0.5, 3.0), 2)
                rssi = round(-95 + confidence * 55 + random.uniform(-3, 3), 1)
                detected_3db_bw = round(random.uniform(1.0, 8.0), 2)
                detected_10db_bw = round(detected_3db_bw + random.uniform(1.0, 5.0), 2)
                ml_detection_status = 1 if confidence >= 0.55 else 0
                azimuth = (bearing + random.uniform(-1.0, 1.0)) % 360
                elevation = round(random.uniform(-5.0, 25.0), 2)
                center_frequency = round(2400 + random.uniform(-20, 20), 2)
                drone_id = random.randint(1, 40) if ml_detection_status else None

                rows.append((
                    random.randint(1, 4),           # modality_id
                    site_id,                         # site_id
                    random.randint(1, 6),            # sdr_detection_param_id
                    random.randint(1, 6),            # sdr_localization_param_id
                    detected_3db_bw,
                    detected_10db_bw,
                    ml_detection_status,
                    confidence,
                    round(azimuth, 2),
                    elevation,
                    random.randint(1, 8),            # antenna_id
                    random.choice(SIGNAL_TYPES),
                    rssi,
                    range_km,                         # "range"
                    '/spectrum/%s/%s.dat' % (cur_date.isoformat(), t.replace(':', '')),
                    center_frequency,
                    1,                                 # _is_active
                    timestamp_str,                      # _last_update_time
                    1,                                   # _last_update_user
                    SEED_TAG,                             # _last_update_remarks
                    5.0,                                   # tolerance
                    drone_id,
                ))
    return rows


INSERT_SQL = """
INSERT INTO rf_detections (
    modality_id, site_id, sdr_detection_param_id, sdr_localization_param_id,
    detected_3db_bw, detected_10db_bw, ml_detection_status, ml_confidence,
    azimuth, elevation, antenna_id, signal_type, rssi, "range",
    spectrum_path, center_frequency, _is_active, _last_update_time,
    _last_update_user, _last_update_remarks, tolerance, drone_id
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def main():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        ensure_table(conn)
        clear_previous_seed(conn)
        rows = build_rows()
        conn.executemany(INSERT_SQL, rows)
        conn.commit()
        print('Inserted %d dummy rows into rf_detections at %s' % (len(rows), DB_PATH))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
