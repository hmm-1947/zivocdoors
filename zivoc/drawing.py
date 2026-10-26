from .core import AppError, fnum, php_wordwrap
from .workflow import wf_number


def wf_xml(value):
    text = '' if value is None else str(value)
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#039;')


def wf_dim(x1, y1, x2, y2, label, vertical=False):
    text_x = (x1 + x2) / 2
    text_y = (y1 + y2) / 2 - 8
    f = fnum
    if vertical:
        ticks = 'M %s %s H %s M %s %s H %s' % (f(x1 - 8), f(y1), f(x1 + 8), f(x2 - 8), f(y2), f(x2 + 8))
    else:
        ticks = 'M %s %s V %s M %s %s V %s' % (f(x1), f(y1 - 8), f(y1 + 8), f(x2), f(y2 - 8), f(y2 + 8))
    rotate = ' transform="rotate(-90 %s %s)"' % (f(text_x), f(text_y + 8)) if vertical else ''
    return (
        '<g stroke="#24334b" stroke-width="1" fill="none"><path d="' + ticks + '"/><path d="M ' + f(x1) + ' ' + f(y1) + ' L ' + f(x2) + ' ' +
        f(y2) + '" marker-start="url(#dim-arrow)" marker-end="url(#dim-arrow)"/></g><text x="' + f(text_x) + '" y="' + f(text_y) +
        '" text-anchor="middle" font-size="12"' + rotate + '>' + wf_xml(label) + '</text>'
    )


def wf_drawing_svg(payload):
    f = fnum
    m = payload['measurement']
    ow = float(m['opening_width'])
    oh = float(m['opening_height'])
    fw = float(m['frame_width'])
    fh = float(m['frame_height'])
    sw = float(m['shutter_width'])
    sh = float(m['shutter_height'])
    wall = float(m['wall_thickness'])
    if min(ow, oh, fw, fh, sw, sh, wall) <= 0:
        raise AppError('Positive survey dimensions required.')
    scale = min(320 / ow, 430 / oh)
    w = ow * scale
    h = oh * scale
    x = 300 - w / 2
    y = 130.0
    fx = x + (ow - fw) * scale / 2
    fy = y + (oh - fh) * scale
    sx = fx + (fw - sw) * scale / 2
    sy = fy + (fh - sh) * scale
    right = m['direction'] == 'Right'
    hinge = sx + sw * scale if right else sx
    opposite = sx if right else sx + sw * scale
    name = wf_xml(m['name'])
    order_id = int(payload['order_id'])
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 920" width="1000" height="920" role="img" '
        'aria-labelledby="drawing-title drawing-desc"><title id="drawing-title">' + name + ' technical door drawing</title>'
        '<desc id="drawing-desc">Dimensioned front elevation and swing plan, in centimetres. Verify on site before manufacture.</desc>'
        '<defs><marker id="dim-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 Z" fill="#24334b"/></marker></defs><rect width="1000" height="920" fill="white"/>'
        '<g font-family="Arial,sans-serif" fill="#17263d"><rect x="24" y="24" width="952" height="872" fill="none" stroke="#24334b"/>'
        '<text x="45" y="57" font-size="21" font-weight="700">FRP DOOR \u2014 TECHNICAL DRAWING</text>'
        '<text x="45" y="82" font-size="13">' + name + ' | Order #' + str(order_id) + ' | Survey r' + str(int(payload['survey_revision'])) +
        ' | Drawing r' + str(int(payload['revision'])) + '</text><path d="M24 96H976" stroke="#24334b"/>'
        '<text x="300" y="117" text-anchor="middle" font-size="12">FRONT ELEVATION \u2014 DIMENSIONS IN cm</text>'
    )
    svg += (
        '<rect x="' + f(x) + '" y="' + f(y) + '" width="' + f(w) + '" height="' + f(h) + '" fill="none" stroke="#8592a6" stroke-dasharray="6 4"/>'
        '<rect x="' + f(fx) + '" y="' + f(fy) + '" width="' + f(fw * scale) + '" height="' + f(fh * scale) +
        '" fill="#f2f4f7" stroke="#17263d" stroke-width="3"/><rect x="' + f(sx) + '" y="' + f(sy) + '" width="' + f(sw * scale) +
        '" height="' + f(sh * scale) + '" fill="white" stroke="#17263d" stroke-width="1.5"/><path d="M ' + f(hinge) + ' ' + f(sy) + ' L ' +
        f(opposite) + ' ' + f(sy + sh * scale / 2) + ' L ' + f(hinge) + ' ' + f(sy + sh * scale) + '" fill="none" stroke="#64748b" stroke-dasharray="5 4"/>'
    )
    svg += (
        '<path d="M ' + f(x) + ' ' + f(y + h) + ' V ' + f(y + h + 48) + ' M ' + f(x + w) + ' ' + f(y + h) + ' V ' + f(y + h + 48) + ' M ' + f(x) + ' ' +
        f(y) + ' H ' + f(x - 58) + ' M ' + f(x) + ' ' + f(y + h) + ' H ' + f(x - 58) + ' M ' + f(fx + fw * scale) + ' ' + f(fy) + ' H ' +
        f(x + w + 48) + ' M ' + f(fx + fw * scale) + ' ' + f(fy + fh * scale) + ' H ' + f(x + w + 48) + '" fill="none" stroke="#8592a6" stroke-width="0.8"/>'
    )
    svg += wf_dim(x, y + h + 40, x + w, y + h + 40, 'Opening W ' + f(ow / 10) + ' cm')
    svg += wf_dim(x - 50, y, x - 50, y + h, 'Opening H ' + f(oh / 10) + ' cm', True)
    svg += wf_dim(fx, y + h + 75, fx + fw * scale, y + h + 75, 'Frame W ' + f(fw / 10) + ' cm')
    svg += wf_dim(x + w + 40, fy, x + w + 40, fy + fh * scale, 'Frame H ' + f(fh / 10) + ' cm', True)
    svg += '<text x="300" y="' + f(y + h / 2) + '" font-size="12" text-anchor="middle">Shutter ' + f(sw / 10) + ' \u00d7 ' + f(sh / 10) + ' cm</text>'
    ps = min(220 / ow, 90 / wall)
    pw = ow * ps
    leaf = sw * ps
    depth = wall * ps
    px = 685 - pw / 2
    py = 380.0
    leaf_x = px + (pw - leaf) / 2
    hx = leaf_x + leaf if right else leaf_x
    end_x = leaf_x if right else leaf_x + leaf
    sign = -1 if m['opening_type'] == 'Inward' else 1
    ey = py + sign * leaf
    sweep = 1 if right else 0
    if sign == 1:
        sweep = 1 - sweep
    svg += (
        '<text x="715" y="151" font-size="13" text-anchor="middle">SWING PLAN</text><rect x="' + f(px - 38) + '" y="' + f(py) +
        '" width="38" height="' + f(depth) + '" fill="#e2e8f0" stroke="#17263d"/><rect x="' + f(px + pw) + '" y="' + f(py) +
        '" width="38" height="' + f(depth) + '" fill="#e2e8f0" stroke="#17263d"/><path d="M ' + f(hx) + ' ' + f(py) + ' L ' + f(hx) + ' ' + f(ey) +
        ' M ' + f(hx) + ' ' + f(py) + ' L ' + f(end_x) + ' ' + f(py) + '" stroke="#17263d" stroke-width="2" fill="none"/><path d="M ' + f(end_x) + ' ' +
        f(py) + ' A ' + f(leaf) + ' ' + f(leaf) + ' 0 0 ' + str(sweep) + ' ' + f(hx) + ' ' + f(ey) +
        '" fill="none" stroke="#24334b" stroke-dasharray="5 3"/><circle cx="' + f(hx) + '" cy="' + f(py) + '" r="4" fill="#17263d"/>'
    )
    svg += wf_dim(px + pw + 62, py, px + pw + 62, py + depth, 'Wall ' + f(wall / 10) + ' cm', True)
    svg += (
        '<text x="715" y="620" text-anchor="middle" font-size="14">' + wf_xml(m['direction'] + ' Hand / ' + m['opening_type']) +
        '</text><text x="715" y="645" text-anchor="middle" font-size="12">Plan: inward is above the wall line</text>'
        '<text x="45" y="680" font-size="13">Location: ' + wf_xml(m['location']) + ' | Quantity: ' + str(int(m['quantity'])) + '</text>'
        '<text x="45" y="705" font-size="11">Parametric schematic \u2014 not to scale on paper. Written dimensions govern manufacture.</text>'
    )
    for annotation in (payload.get('annotations') or [])[:8]:
        ax = 100 + wf_number(annotation['x'], 0, 100) * 8
        ay = 130 + wf_number(annotation['y'], 0, 100) * 4.8
        svg += (
            '<g><circle cx="' + f(ax) + '" cy="' + f(ay) + '" r="3" fill="#a02b2b"/><text x="' + f(ax + 7) + '" y="' + f(ay - 7) +
            '" font-size="11" fill="#a02b2b">' + wf_xml(annotation['text']) + '</text></g>'
        )
    notes = 'Drawing notes: ' + str(payload.get('notes') or '') + ' | Site: ' + str(m.get('site_notes') or '') + ' | Special: ' + str(m.get('requirements') or '')
    wrapped = php_wordwrap(notes, 120)
    for index, line in enumerate(wrapped[:9]):
        svg += '<text x="45" y="' + str(735 + index * 16) + '" font-size="11">' + wf_xml(line) + '</text>'
    if len(wrapped) > 9:
        svg += '<text x="45" y="885" font-size="10">Additional notes are available in the saved survey/drawing record.</text>'
    suffix = '-%d-%d-%d' % (order_id, int(m.get('id') or 0), int(payload['revision']))
    svg += '</g></svg>'
    return svg.replace('dim-arrow', 'dim-arrow' + suffix).replace('drawing-title', 'drawing-title' + suffix).replace('drawing-desc', 'drawing-desc' + suffix)
