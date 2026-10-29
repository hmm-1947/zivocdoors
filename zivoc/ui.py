from markupsafe import Markup, escape

from . import db
from .core import money, php_date, wf_money
from .helpers import csrf_token, privileged

ICON_PATHS = {
    'home': 'M3 10 12 3l9 7v11h-6v-7H9v7H3Z',
    'leads': 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
    'orders': 'M6 3h12v18H6ZM9 7h6M9 11h6M9 15h4',
    'products': 'M3 5h18v4H3ZM5 9v12h14V9M9 13h6',
    'profile': 'M20 21a8 8 0 0 0-16 0M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
    'plus': 'M12 5v14M5 12h14',
    'menu': 'M4 6h16M4 12h16M4 18h16',
    'bell': 'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',
    'phone': 'M5 3h4l2 5-3 2a16 16 0 0 0 6 6l2-3 5 2v4c-9 4-22-9-16-16Z',
    'chart': 'M5 20v-7M12 20V4M19 20v-11',
    'arrow': 'M9 5l7 7-7 7',
    'check': 'm5 12 4 4L19 6',
    'pin': 'M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0ZM15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0',
    'calendar': 'M3 6h18v15H3ZM3 10h18M8 3v5M16 3v5',
    'wallet': 'M3 5h17v16H3ZM3 5V3h14M15 11h6v5h-6Z',
}


def icon(name):
    path = ICON_PATHS.get(name, ICON_PATHS['orders'])
    return Markup('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
                  'stroke-linejoin="round" aria-hidden="true"><path d="%s"/></svg>') % path


def start_form(action, css='', multipart=False):
    return Markup('<form method="post" class="%s"%s><input type="hidden" name="csrf" value="%s"><input type="hidden" name="action" value="%s">') % (
        css, Markup(' enctype="multipart/form-data"' if multipart else ''), csrf_token(), action)


def field(label, name, kind='text', value='', required=True):
    extra = ''
    if kind == 'number':
        extra += ' min="0" step="0.01"'
    if kind == 'password':
        extra += ' minlength="12"'
    return Markup('<label>%s<input name="%s" type="%s" value="%s" %s%s></label>') % (
        label, name, kind, '' if value is None else value, 'required' if required else '', Markup(extra))


def area(label, name, value=''):
    return Markup('<label>%s<textarea name="%s" required>%s</textarea></label>') % (label, name, '' if value is None else value)


def assignment(u):
    if not privileged(u):
        return Markup('')
    options = Markup('').join(
        Markup('<option value="%s">%s</option>') % (row['id'], '%s \u00b7 %s' % (row['name'], str(row['role']).capitalize()))
        for row in db.rows("SELECT id,name,role FROM users WHERE role IN ('salesman','freelancer','fabricator') AND active=1 ORDER BY name")
    )
    return Markup('<label>Assign salesman / freelancer<select name="salesman_id" required><option value="">Select salesman or freelancer</option>%s</select></label>') % options


def submit(label='Save'):
    return Markup('<button type="submit">%s</button></form>') % label


def empty_state(text):
    return Markup('<div class="empty">%s<p>%s</p></div>') % (icon('orders'), text)


def tasks(items):
    if not items:
        return empty_state('You\u2019re all caught up. Add a follow-up to stay on track.')
    out = []
    for task in items:
        link = Markup('<a href="?page=order&id=%d">Order #%d</a>') % (int(task['order_id']), int(task['order_id'])) if task['order_id'] else Markup('')
        out.append(
            Markup('<article class="task"><span class="task-mark">%s</span><div><strong>%s</strong><small>%s \u00b7 %s</small>%s</div>%s'
                   '<input type="hidden" name="id" value="%d"><button class="icon-button" aria-label="Complete reminder">%s</button></form></article>') % (
                icon('phone'), task['title'], php_date('d M, h:i a', task['due_at']), task['name'], link, start_form('done'), int(task['id']), icon('check')))
    return Markup('').join(out)


def register(app):
    app.jinja_env.globals.update(
        icon=icon,
        start_form=start_form,
        field=field,
        area=area,
        assignment=assignment,
        submit=submit,
        empty_state=empty_state,
        tasks=tasks,
        money=money,
        wf_money=wf_money,
        php_date=php_date,
    )
