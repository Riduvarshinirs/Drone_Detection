# RF Case - Drone Detection Console

Django web app for the RF drone-detection dashboard: a top-down "radar
scope" (PPI style) with range rings. Pick a From/To date and time
range and it draws two views side by side:

- Case 1 (left): a continuous 360-degree color gradient (blue -> green
  -> amber -> red) showing detection confidence at every bearing, plus
  a text readout of the strongest bearings in that sweep.
- Case 2 (right): a density heatmap of filled bearing/range patches,
  showing where detections cluster, plus a readout of the busiest
  patches.

Data now comes from a real table, `rf_detections`, living in
`db.sqlite3` - built from the PostgreSQL schema sir provided (see
`create_table.sql`). The old Excel-based dummy data has been retired;
dummy rows are seeded straight into that same table instead, so the
whole app is already wired end to end the way it will work once sir's
real data starts landing in the table.

## What is in here

```
drone/
  manage.py
  requirements.txt
  create_table.sql             rf_detections schema (SQLite translation of sir's Postgres DDL)
  db.sqlite3                   the actual database - holds rf_detections plus Django's own tables
  rfradar/                     Django project settings
    settings.py
    urls.py, wsgi.py, asgi.py
  rfapp/
    views.py                   radar_view - reads GET params, calls db_reader, builds context
    db_reader.py                ALL database I/O + aggregation lives here - this is the
                                  one file to change if the table/column names change again
    scope_plotly.py             builds the Case 1 gradient figure (plain dict, no CDN needed)
    heatmap_plotly.py           builds the Case 2 patch-heatmap figure
    urls.py
    templates/rfapp/radar.html  From/To date+time pickers, both plots, legends, readout panels
    static/rfapp/plotly.min.js  Plotly.js bundled locally - NO CDN, works fully offline
  data/
    generate_dummy_data.py      seeds rf_detections with throwaway dummy rows (stdlib only)
```

## rf_detections schema

`create_table.sql` is the SQLite translation of the PostgreSQL schema
sir sent. Column-by-column notes (Postgres type -> SQLite type):

| column                     | type (Postgres)        | SQLite type | notes                                  |
|----------------------------|-------------------------|-------------|------------------------------------------|
| rf_detection_id            | integer, PK              | INTEGER PK  | autoincrement                            |
| modality_id                | integer                  | INTEGER     |                                            |
| site_id                    | uuid                      | TEXT        | 36-char uuid string                       |
| sdr_detection_param_id     | integer                  | INTEGER     |                                            |
| sdr_localization_param_id  | integer                  | INTEGER     |                                            |
| detected_3db_bw            | double precision          | REAL        |                                            |
| detected_10db_bw           | double precision          | REAL        |                                            |
| ml_detection_status        | boolean                  | INTEGER     | 0 / 1                                     |
| ml_confidence               | double precision          | REAL        | 0.0 - 1.0                                 |
| azimuth                     | double precision          | REAL        | bearing, degrees, 0 = N, clockwise        |
| elevation                   | double precision          | REAL        |                                            |
| antenna_id                  | integer                  | INTEGER     |                                            |
| signal_type                 | varchar(256)              | TEXT        | nullable                                  |
| rssi                         | double precision          | REAL        | nullable                                  |
| range                        | double precision          | REAL        | nullable, assumed km                      |
| spectrum_path                | varchar(1024)             | TEXT        | nullable                                  |
| center_frequency              | double precision          | REAL        | default 2400                              |
| _is_active                    | boolean                  | INTEGER     | default 1; soft-delete flag               |
| _last_update_time              | timestamp                | TEXT        | "YYYY-MM-DD HH:MM:SS", default now        |
| _last_update_user               | integer                  | INTEGER     |                                            |
| _last_update_remarks             | varchar(256)              | TEXT        | nullable                                  |
| tolerance                        | double precision          | REAL        | default 5                                 |
| drone_id                          | integer                  | INTEGER     | nullable                                  |

To (re)create the table by hand:

```bash
python manage.py dbshell
sqlite> .read create_table.sql
sqlite> .quit
```

## How db_reader.py maps the table to the dashboard

`rfapp/db_reader.py` reads every row where `_is_active = 1` and turns
it into the same plain-dict shape the app has always worked with:

| dashboard field | comes from                                             |
|------------------|----------------------------------------------------------|
| date / time       | `_last_update_time`, split into `YYYY-MM-DD` and `HH:MM` - this drives the From/To dropdowns |
| bearing_deg        | `azimuth`, rounded to the nearest whole degree             |
| range_km            | `range`                                                     |
| rf_value             | `ml_confidence * 100` (0-1 scaled up to 0-100, so `DETECTION_THRESHOLD = 55.0` still lines up with "confidence >= 0.55") |

That mapping is the only assumption baked in right now, since the
exact meaning of a few columns (e.g. whether `range` is really in km)
was not spelled out. If any of it is wrong, it is a one-place fix in
`db_reader.py` - nothing else in the app needs to change.

## How to run

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py dbshell
sqlite> .read create_table.sql
sqlite> .quit
cd data && python generate_dummy_data.py && cd ..
python manage.py runserver
```

Open http://127.0.0.1:8000/ - pick a date/time range on either side
and hit "Update Scope".

## Regenerating dummy data

```bash
cd data
python generate_dummy_data.py
```

Standard library only (sqlite3, random, uuid, datetime - no openpyxl,
no Django needed to run it). It creates `rf_detections` if it is not
there yet (via `create_table.sql`), clears out rows from any previous
run of this script, and inserts 14 days x 6 timestamps x 72 bearings
(every 5 degrees) of dummy readings, with 1-3 randomly placed
"hotspot" bearings per timestamp so `ml_confidence` spikes near a
moving cluster instead of being random noise everywhere.

## Swapping in sir's real data

Once real rows start landing in `rf_detections`, there is nothing left
to swap - `db_reader.py` already reads from that exact table. Just
stop running `generate_dummy_data.py`. If a column gets renamed or a
new one shows up that the dashboard should use instead (e.g. a
different confidence/strength field), the only file to touch is
`rfapp/db_reader.py`; `views.py`, `scope_plotly.py`, `heatmap_plotly.py`
and the template do not know or care where the numbers came from.

## Offline / Windows notes

- `rfapp/static/rfapp/plotly.min.js` is bundled locally (no CDN calls
  anywhere) so the offline Windows viewing client can load it.
- Every `.py`, `.html` and `.sql` file in this project is pure ASCII -
  required because non-ASCII bytes have previously corrupted files in
  transit from the Linux dev machine to the Windows client.
- The template has a try/catch around each `Plotly.newPlot` call so a
  client-side failure shows a visible red error message instead of a
  silent blank plot.
