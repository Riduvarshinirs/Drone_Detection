from .scope_plotly import intensity_to_rgb, MAX_RANGE_KM as CASE1_MAX_RANGE_K

PATCH_ARC_STEPS = 6        # points sampled along each curved edge
BEARING_GAP_FRAC = 0.10    # fraction of a cell's angular width left as a gap
RANGE_GAP_FRAC = 0.12      # fraction of a cell's radial depth left as a gap


def _wedge_path(theta0, theta1, r0, r1, arc_steps=PATCH_ARC_STEPS):
    """Outline of a ring-segment (annular sector) from theta0->theta1 at
    r1 (outer arc), then back theta1->theta0 at r0 (inner arc), closed."""
    thetas, rs = [], []
    for i in range(arc_steps + 1):
        t = theta0 + (theta1 - theta0) * i / arc_steps
        thetas.append(t)
        rs.append(r1)
    for i in range(arc_steps + 1):
        t = theta1 - (theta1 - theta0) * i / arc_steps
        thetas.append(t)
        rs.append(r0)
    thetas.append(thetas[0])
    rs.append(rs[0])
    return thetas, rs


def _patch_traces(cells):
    """One filled, borderless wedge trace per cell - non-overlapping by
    construction, since each wedge is clipped to its own bearing/range
    box with a small gap left around it for visual separation."""
    max_readings = max((c['reading_count'] for c in cells), default=1) or 1
    traces = []

    for c in cells:
        bearing_width = c['bearing_width_deg']
        gap_deg = bearing_width * BEARING_GAP_FRAC
        theta0 = c['bearing_deg'] - bearing_width / 2.0 + gap_deg / 2.0
        theta1 = c['bearing_deg'] + bearing_width / 2.0 - gap_deg / 2.0

        depth = max(c['r_end'] - c['r_start'], 0.001)
        gap_r = depth * RANGE_GAP_FRAC
        r0 = c['r_start'] + gap_r / 2.0
        r1 = max(c['r_end'] - gap_r / 2.0, r0 + 0.01)

        thetas, rs = _wedge_path(theta0, theta1, r0, r1)
        color = intensity_to_rgb(c['intensity'])
        density_t = (c['reading_count'] / max_readings) ** 0.5
        opacity = round(0.55 + 0.4 * density_t, 3)

        hover_text = (
            'Bearing %.0f deg<br>'
            'Range %.2f-%.2f km<br>'
            'Detections %d / %d<br>'
            'Avg RF value %.1f<br>'
            'Peak RF value %.1f'
        ) % (
            c['bearing_deg'], c['r_start'], c['r_end'],
            c['detection_count'], c['reading_count'],
            c['avg_rf_value'], c['max_rf_value'],
        )

       

    
 
        traces.append({
            'type': 'scatterpolar',
            'r': [(c['r_start'] + c['r_end']) / 2],
            
        'theta': [c['bearing_deg']],
    'mode': 'markers',
    'marker': {
        'symbol': 'circle',
        'size': 20,
        'color': color,
        'opacity': opacity,
        'line': {
            'width': 1,
            'color': '#05080a'
        }
    },
            'fill': 'toself',
            'fillcolor': color,
            'opacity': opacity,
            'line': {'width': 0.5, 'color': color},
            'hoveron': 'fills',
            'hoverinfo': 'text',
            'text': [hover_text] ,
            'showlegend': False,
        })

    return traces


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


def build_heatmap_figure(cells, max_range_km=CASE1_MAX_RANGE_KM):
    data = []

    if cells:
        data.extend(_patch_traces(cells))

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
                'range': [0, max_range_km],
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
