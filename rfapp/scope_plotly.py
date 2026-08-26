MAX_RANGE_KM = 3.2

COLOR_LOW = (46, 111, 255)     # blue    - low intensity
COLOR_MID1 = (46, 255, 170)    # green
COLOR_MID2 = (255, 178, 56)    # amber
COLOR_HIGH = (255, 59, 59)     # red     - high intensity


def _lerp(a, b, t):
    return a + (b - a) * t


def intensity_to_rgb(t):
    """0.0 -> blue, ~0.33 -> green, ~0.66 -> amber, 1.0 -> red."""
    t = max(0.0, min(1.0, t))
    if t < 1 / 3:
        seg_t = t / (1 / 3)
        c0, c1 = COLOR_LOW, COLOR_MID1
    elif t < 2 / 3:
        seg_t = (t - 1 / 3) / (1 / 3)
        c0, c1 = COLOR_MID1, COLOR_MID2
    else:
        seg_t = (t - 2 / 3) / (1 / 3)
        c0, c1 = COLOR_MID2, COLOR_HIGH
    r = round(_lerp(c0[0], c1[0], seg_t))
    g = round(_lerp(c0[1], c1[1], seg_t))
    b = round(_lerp(c0[2], c1[2], seg_t))
    return 'rgb(%d,%d,%d)' % (r, g, b)

_intensity_to_rgb = intensity_to_rgb


def _gradient_trace(segments):
    """One borderless barpolar trace covering the whole 360-degree
    sweep. Each segment is a thin wedge (1 degree wide by default)
    sitting flush against its neighbours, coloured from the smoothed
    intensity computed in db_reader.aggregate_gradient. Because the
    wedges are thin, borderless, and pre-smoothed, the whole thing
    reads as one continuous red-to-blue gradient rather than a set of
    separate cone shapes.
    """
    if not segments:
        return None

    thetas = [s['bearing_center'] for s in segments]
    r_vals = [s['range_km'] for s in segments]
    colors = [
        '#000000' if s.get('no_data') else _intensity_to_rgb(s['intensity'])
        for s in segments
    ]

    if len(segments) > 1:
        step = segments[1]['bearing_center'] - segments[0]['bearing_center']
        if step <= 0:
            step = 360.0 / len(segments)
    else:
        step = 360.0
    widths = [step] * len(segments)

    customdata = [
        [s['bearing_center'], s['range_km'], s['rf_value'], round(s['intensity'] * 100)]
        for s in segments
    ]

    return {
        'type': 'barpolar',
        'r': r_vals,
        'theta': thetas,
        'width': widths,
        'marker': {
            'color': colors,
            'line': {'width': 0},
        },
        'opacity': 0.92,
        'customdata': customdata,
        'hovertemplate': (
            'Bearing %{customdata[0]:.0f} deg<br>'
            'Range ~%{customdata[1]:.2f} km<br>'
            'RF value %{customdata[2]}<br>'
            'Signal strength %{customdata[3]}%'
            '<extra></extra>'
        ),
        'showlegend': False,
    }


def _peak_markers_trace(peaks):
    """Small open-ring markers over the gradient marking the standout
    bearings listed in the readout panel - reference points only, they
    don't add any hard edges of their own."""
    if not peaks:
        return None

    thetas = [p['bearing_deg'] for p in peaks]
    r_vals = [max(p['range_km'], 0.05) for p in peaks]
    customdata = [[p['bearing_deg'], p['range_km'], p['rf_value']] for p in peaks]

    return {
        'type': 'scatterpolar',
        'r': r_vals,
        'theta': thetas,
        'mode': 'markers',
        'marker': {
            'size': 10,
            'symbol': 'circle-open',
            'color': 'rgba(255,255,255,0.95)',
            'line': {'width': 2, 'color': 'rgba(255,255,255,0.95)'},
        },
        'customdata': customdata,
        'hovertemplate': (
            'Peak bearing %{customdata[0]:.0f} deg<br>'
            'Range ~%{customdata[1]:.2f} km<br>'
            'RF value %{customdata[2]}'
            '<extra></extra>'
        ),
        'showlegend': False,
    }


def _center_dot_trace():
    return {
        'type': 'scatterpolar',
        'r': [0],
        'theta': [0],
        'mode': 'markers',
        'marker': {'size': 10, 'color': '#ffb238', 'line': {'color': '#1a1200', 'width': 1}},
        'hoverinfo': 'skip',
        'showlegend': False,
    }


def build_scope_figure(rows, segments, peaks=None):
    data = []

    gradient_trace = _gradient_trace(segments)
    if gradient_trace:
        data.append(gradient_trace)

    peak_trace = _peak_markers_trace(peaks)
    if peak_trace:
        data.append(peak_trace)

    data.append(_center_dot_trace())

    layout = {
        'paper_bgcolor': '#05080a',
        'plot_bgcolor': '#05080a',
        'showlegend': False,
        'margin': {'l': 40, 'r': 40, 't': 30, 'b': 30},
        'height': 560,
        'width': 560,
        'font': {'color': '#cfe8e6', 'family': 'Consolas, monospace', 'size': 11},
        'polar': {
            'bgcolor': '#05080a',
            'radialaxis': {
                'range': [0, MAX_RANGE_KM],
                'tickvals': [1, 2, 3],
                'ticktext': ['1 km', '2 km', '3 km'],
                'gridcolor': '#16444a',
                'linecolor': '#16444a',
                'tickfont': {'color': '#5d7d7d', 'size': 10},
                'angle': 90,
            },
            'angularaxis': {
                'tickvals': [0, 90, 180, 270],
                'ticktext': ['N', 'E', 'S', 'W'],
                'gridcolor': '#16444a',
                'linecolor': '#16444a',
                'direction': 'clockwise',
                'rotation': 90,
                'tickfont': {'color': '#5d7d7d', 'size': 11},
            },
        },
    }

    return {'data': data, 'layout': layout}
