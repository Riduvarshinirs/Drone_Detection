
from django.db import connection
from django.db.utils import OperationalError

DETECTION_THRESHOLD = 55.0

CONFIDENCE_TO_RF_SCALE = 100.0

_ROWS_SQL = (
    'SELECT azimuth, "range", ml_confidence, '
    "strftime('%Y-%m-%d', _last_update_time) AS reading_date, "
    "strftime('%H:%M', _last_update_time) AS reading_time "
    'FROM rf_detections '
    'WHERE _is_active = 1'
)


def _load_rows():
    """Read every active row from rf_detections into a list of plain
    dicts shaped like the rest of the app expects. Returns an empty
    list (instead of raising) if the table has not been created yet -
    see create_table.sql - so the page still renders its "no data"
    state instead of a 500.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute(_ROWS_SQL)
            raw_rows = cursor.fetchall()
    except OperationalError:
        return []

    rows = []
    for azimuth, range_km, confidence, reading_date, reading_time in raw_rows:
        if azimuth is None or range_km is None or confidence is None:
            continue
        if reading_date is None or reading_time is None:
            continue
        try:
            rows.append({
                'date': reading_date,
                'time': reading_time,
                'bearing_deg': int(round(float(azimuth))) % 360,
                'range_km': float(range_km),
                'rf_value': round(float(confidence) * CONFIDENCE_TO_RF_SCALE, 1),
            })
        except (TypeError, ValueError):
            continue

    return rows


def get_available_dates():
    rows = _load_rows()
    return sorted(set(r['date'] for r in rows))


def get_available_times():
    rows = _load_rows()
    return sorted(set(r['time'] for r in rows))


def get_readings_between(from_date, to_date, from_time=None, to_time=None):
    """Filter rows by an inclusive date range and, optionally, an
    inclusive time-of-day range applied on every day in that span.

    Time strings are zero-padded 24h "HH:MM", so plain string
    comparison sorts them correctly - no need to parse into a
    datetime.time object.
    """
    rows = _load_rows()
    result = []
    for r in rows:
        if not (from_date <= r['date'] <= to_date):
            continue
        if from_time is not None and to_time is not None:
            if not (from_time <= r['time'] <= to_time):
                continue
        result.append(r)
    return result


GRADIENT_BUCKET_DEG = 5     # matches the raw data's bearing grid
GRADIENT_UPSAMPLE_DEG = 1   # final render resolution (finer = smoother)
GRADIENT_SMOOTH_RADIUS = 4  # how many neighbouring buckets blend together

GRADIENT_FINE_SMOOTH_RADIUS_DEG = 6    # +/- degrees blended in the fine pass
GRADIENT_FINE_SMOOTH_SIGMA_DEG = 3.0   # how tightly weighted around center


def aggregate_gradient(rows, bucket_deg=GRADIENT_BUCKET_DEG,
                        upsample_deg=GRADIENT_UPSAMPLE_DEG,
                        smooth_radius=GRADIENT_SMOOTH_RADIUS):
    """Build a full 360-degree intensity/range profile from every row
    in `rows` (no top-N cut-off, no detection threshold).

    Bearing buckets that had zero raw readings on both sides of an
    interpolated stretch are flagged 'no_data' so the renderer can
    paint that stretch pure black instead of guessing a color for it -
    "no signal" and "signal too weak to matter" are different things
    and should not look the same on the scope.
    """
    if not rows:
        return []

    num_buckets = 360 // bucket_deg

    sum_rf = [0.0] * num_buckets
    sum_range = [0.0] * num_buckets
    count = [0] * num_buckets

    for r in rows:
        idx = int(r['bearing_deg'] // bucket_deg) % num_buckets
        sum_rf[idx] += r['rf_value']
        sum_range[idx] += r['range_km']
        count[idx] += 1

    raw_has_data = [count[i] > 0 for i in range(num_buckets)]
    raw_rf = [sum_rf[i] / count[i] if count[i] else None for i in range(num_buckets)]
    raw_range = [sum_range[i] / count[i] if count[i] else None for i in range(num_buckets)]

    def fill_gaps(arr):
        """Any bearing bucket with zero readings borrows a value from
        its nearest neighbours, purely so the interpolation below has
        numbers to work with - the 'no_data' flag (tracked separately
        via raw_has_data) is what actually controls the black-out, not
        this borrowed value."""
        if all(v is None for v in arr):
            return [0.0] * len(arr)
        filled = list(arr)
        n = len(filled)
        for i in range(n):
            if filled[i] is not None:
                continue
            for radius in range(1, n):
                lo = arr[(i - radius) % n]
                hi = arr[(i + radius) % n]
                found = [v for v in (lo, hi) if v is not None]
                if found:
                    filled[i] = sum(found) / len(found)
                    break
            if filled[i] is None:
                filled[i] = 0.0
        return filled

    raw_rf = fill_gaps(raw_rf)
    raw_range = fill_gaps(raw_range)

    def smooth(arr):
        """Circular weighted-average smoothing across neighbouring
        buckets - this is what removes the hard edges between
        neighbouring bearings."""
        n = len(arr)
        out = []
        for i in range(n):
            total, weight = 0.0, 0.0
            for off in range(-smooth_radius, smooth_radius + 1):
                w = 1.0 - (abs(off) / (smooth_radius + 1))
                total += arr[(i + off) % n] * w
                weight += w
            out.append(total / weight if weight else 0.0)
        return out

    smooth_rf = smooth(raw_rf)
    smooth_range = smooth(raw_range)

    def smoothstep(t):
        """Eases in/out of each bucket-to-bucket transition instead of
        a straight linear ramp, so the fine-grained curve has no sharp
        corner sitting exactly on top of each old bucket boundary."""
        return t * t * (3.0 - 2.0 * t)


    steps_per_bucket = max(1, round(bucket_deg / upsample_deg))
    fine_rf, fine_range, fine_bearing, fine_no_data = [], [], [], []
    for i in range(num_buckets):
        rf0, rf1 = smooth_rf[i], smooth_rf[(i + 1) % num_buckets]
        rg0, rg1 = smooth_range[i], smooth_range[(i + 1) % num_buckets]
        pair_has_no_data = (not raw_has_data[i]) and (not raw_has_data[(i + 1) % num_buckets])
        center0 = i * bucket_deg + bucket_deg / 2.0
        for s in range(steps_per_bucket):
            t = smoothstep(s / steps_per_bucket)
            fine_rf.append(rf0 + (rf1 - rf0) * t)
            fine_range.append(rg0 + (rg1 - rg0) * t)
            fine_bearing.append((center0 + s * upsample_deg) % 360)
            fine_no_data.append(pair_has_no_data)

    def gaussian_smooth_circular(arr, radius_deg, sigma_deg, step_deg):
        """A second, finer smoothing pass over the upsampled curve
        itself (not just bucket-to-bucket), so the visible wave has no
        residual facets left over from the original 5-degree grid."""
        radius = max(1, round(radius_deg / step_deg))
        sigma = max(0.5, sigma_deg / step_deg)
        weights = [pow(2.718281828, -0.5 * (k / sigma) ** 2) for k in range(-radius, radius + 1)]
        n = len(arr)
        out = []
        for i in range(n):
            total, wsum = 0.0, 0.0
            for k in range(-radius, radius + 1):
                w = weights[k + radius]
                total += arr[(i + k) % n] * w
                wsum += w
            out.append(total / wsum if wsum else arr[i])
        return out

    fine_rf = gaussian_smooth_circular(
        fine_rf, GRADIENT_FINE_SMOOTH_RADIUS_DEG, GRADIENT_FINE_SMOOTH_SIGMA_DEG, upsample_deg)
    fine_range = gaussian_smooth_circular(
        fine_range, GRADIENT_FINE_SMOOTH_RADIUS_DEG, GRADIENT_FINE_SMOOTH_SIGMA_DEG, upsample_deg)

    rf_min = min(fine_rf)
    rf_max = max(fine_rf)
    span = (rf_max - rf_min) or 1.0

    segments = []
    for bearing, rf, rng, no_data in zip(fine_bearing, fine_rf, fine_range, fine_no_data):
        intensity = 0.0 if no_data else (rf - rf_min) / span
        segments.append({
            'bearing_center': bearing,
            'range_km': round(max(rng, 0.05), 3),
            'rf_value': round(rf, 1),
            'intensity': round(intensity, 3),
            'no_data': no_data,
        })

    segments.sort(key=lambda s: s['bearing_center'])
    return segments


def find_gradient_peaks(segments, top_n=3, min_separation_deg=25):
    """Pull out a handful of standout bearings from the gradient, purely
    for the text readout panel - the plotted disc itself always shows
    the full continuous sweep, not just these peaks."""
    if not segments:
        return []

    def circ_dist(a, b):
        d = abs(a - b) % 360
        return min(d, 360 - d)

    candidates = [s for s in segments if not s.get('no_data')] or segments
    ranked = sorted(candidates, key=lambda s: s['intensity'], reverse=True)
    peaks = []
    for s in ranked:
        if all(circ_dist(s['bearing_center'], p['bearing_deg']) >= min_separation_deg for p in peaks):
            peaks.append({
                'bearing_deg': int(round(s['bearing_center'])) % 360,
                'range_km': s['range_km'],
                'rf_value': s['rf_value'],
                'intensity': s['intensity'],
            })
        if len(peaks) >= top_n:
            break
    return peaks


HEATMAP_MAX_RANGE_KM = 3.2


def aggregate_heatmap(rows, bearing_bucket_deg=15, range_bucket_km=0.5,
                       max_range_km=HEATMAP_MAX_RANGE_KM, top_n=3):

    if not rows:
        return [], []

    buckets = {}
    for r in rows:
        if r['range_km'] > max_range_km:
            continue
        b_idx = int(r['bearing_deg'] // bearing_bucket_deg)
        rng_idx = int(r['range_km'] // range_bucket_km)
        key = (b_idx, rng_idx)
        b = buckets.setdefault(key, [])
        b.append(r['rf_value'])

    cells = []
    for (b_idx, rng_idx), rfs in buckets.items():
        detection_count = sum(1 for v in rfs if v >= DETECTION_THRESHOLD)
        if detection_count == 0:
            continue

        r_start = rng_idx * range_bucket_km
        r_end = min(r_start + range_bucket_km, max_range_km)

        cells.append({
            'bearing_deg': b_idx * bearing_bucket_deg + bearing_bucket_deg / 2,
            'bearing_width_deg': bearing_bucket_deg,
            'r_start': round(r_start, 3),
            'r_end': round(r_end, 3),
            'range_km': round((r_start + r_end) / 2, 2),
            'detection_count': detection_count,
            'reading_count': len(rfs),
            'avg_rf_value': round(sum(rfs) / len(rfs), 1),
            'max_rf_value': round(max(rfs), 1),
        })

    if not cells:
        return [], []

    max_count = max(c['detection_count'] for c in cells) or 1
    max_rf = max(c['max_rf_value'] for c in cells) or 1
    for c in cells:
        count_score = c['detection_count'] / max_count
        rf_score = c['max_rf_value'] / max_rf if max_rf else 0
        c['intensity'] = round(0.65 * count_score + 0.35 * rf_score, 3)

    cells.sort(key=lambda c: (c['detection_count'], c['max_rf_value']), reverse=True)
    top_patches = cells[:top_n]

    return cells, top_patches
