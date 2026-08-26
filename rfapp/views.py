from django.shortcuts import render

from . import db_reader
from . import scope_plotly
from . import heatmap_plotly

RANK_LABELS = ['Strongest', '2nd strongest', '3rd strongest']


def radar_view(request):
    available_dates = db_reader.get_available_dates()

    if not available_dates:
        return render(request, 'rfapp/radar.html', {
            'available_dates': [],
            'available_times': [],
            'no_data': True,
        })

    available_times = db_reader.get_available_times()

    default_from_date = available_dates[0]
    default_to_date = available_dates[-1]
    default_from_time = available_times[0] if available_times else None
    default_to_time = available_times[-1] if available_times else None

    from_date = request.GET.get('from_date', default_from_date)
    to_date = request.GET.get('to_date', default_to_date)
    from_time = request.GET.get('from_time', default_from_time)
    to_time = request.GET.get('to_time', default_to_time)

    if from_date not in available_dates:
        from_date = default_from_date
    if to_date not in available_dates:
        to_date = default_to_date
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    if available_times:
        if from_time not in available_times:
            from_time = default_from_time
        if to_time not in available_times:
            to_time = default_to_time
        if from_time > to_time:
            from_time, to_time = to_time, from_time

    rows = db_reader.get_readings_between(from_date, to_date, from_time, to_time)

   
    gradient_segments = db_reader.aggregate_gradient(rows)
    peaks = db_reader.find_gradient_peaks(gradient_segments, top_n=3)

    for i, p in enumerate(peaks):
        p['rank_label'] = RANK_LABELS[i] if i < len(RANK_LABELS) else 'Detected'
        p['probability_pct'] = round(p['intensity'] * 100)
        p['swatch_color'] = scope_plotly.intensity_to_rgb(p['intensity'])

    scope_figure = scope_plotly.build_scope_figure(rows, gradient_segments, peaks)

    heatmap_cells, top_patches = db_reader.aggregate_heatmap(rows, top_n=3)

    for i, p in enumerate(top_patches):
        p['rank_label'] = RANK_LABELS[i] if i < len(RANK_LABELS) else 'Detected'
        p['probability_pct'] = round(p['intensity'] * 100)
        p['swatch_color'] = scope_plotly.intensity_to_rgb(p['intensity'])

    heatmap_figure = heatmap_plotly.build_heatmap_figure(heatmap_cells)

    context = {
        'available_dates': available_dates,
        'available_times': available_times,
        'selected_from': from_date,
        'selected_to': to_date,
        'selected_from_time': from_time,
        'selected_to_time': to_time,
        'peaks': peaks,
        'scope_figure': scope_figure,
        'top_patches': top_patches,
        'heatmap_figure': heatmap_figure,
        'reading_count': len(rows),
        'no_data': False,
    }
    return render(request, 'rfapp/radar.html', context)
