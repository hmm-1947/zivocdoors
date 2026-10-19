import re
from datetime import datetime, timedelta

from flask import request

from . import db
from .core import AppError, is_array, now, php_date, php_round, post, to_dt, today
from .helpers import positive, required, require_admin, to_int, val

MONTH_RE = re.compile(r'^(20[0-9]{2})-(0[1-9]|1[0-2])$')


def hr_month(month):
    if not MONTH_RE.match(month):
        raise AppError('Select a valid month between 2000 and 2099.')
    return month


def hr_date(value):
    try:
        parsed = datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        parsed = None
    if parsed is None or parsed.strftime('%Y-%m-%d') != value or value < '2000-01-01' or value > '2099-12-31':
        raise AppError('Enter a valid date between 2000 and 2099.')
    return value


def hr_employee(u, employee_id=None):
    if u['role'] == 'admin':
        requested = employee_id if employee_id is not None else request.args.get('employee_id')
        uid = to_int(requested) if requested is not None else int(u['id'])
    else:
        uid = int(u['id'])
    employee = db.one('SELECT id,name,role FROM users WHERE id=%s', [uid])
    if not employee:
        raise AppError('Employee unavailable.')
    return employee


def hr_salesman(user_id):
    employee = db.one("SELECT id,name FROM users WHERE id=%s AND role='salesman'", [user_id])
    if not employee:
        raise AppError('Select a salesman.')
    return employee


def hr_lock(user_id):
    db.q('SELECT id FROM users WHERE id=%s FOR UPDATE', [user_id]).close()


def hr_workdays():
    row = db.one("SELECT setting_value FROM hr_settings WHERE setting_key='working_days'")
    value = row['setting_value'] if row else '1,2,3,4,5,6'
    return [to_int(part) for part in value.split(',')]


def hr_attendance(month, uid):
    first = to_dt(hr_month(month) + '-01')
    last_day = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    end = last_day.strftime('%Y-%m-%d')
    start = first.strftime('%Y-%m-%d')
    current = today()
    workdays = hr_workdays()
    punches = {}
    for row in db.rows('SELECT day,punched_at FROM attendance WHERE user_id=%s AND day BETWEEN %s AND %s', [uid, start, end]):
        punches[row['day']] = row
    leaves = db.rows(
        "SELECT * FROM leave_requests WHERE user_id=%s AND status IN ('pending','approved') AND start_date<=%s AND end_date>=%s",
        [uid, end, start],
    )
    days = []
    counts = {'working': 0, 'present': 0, 'leave': 0, 'absent': 0, 'off': 0}
    date = first
    while date.strftime('%Y-%m-%d') <= end:
        day = date.strftime('%Y-%m-%d')
        work = date.isoweekday() in workdays
        leave = None
        pending = False
        for item in leaves:
            if item['start_date'] <= day <= item['end_date']:
                if item['status'] == 'approved':
                    leave = item
                else:
                    pending = True
        if work:
            counts['working'] += 1
        if day in punches:
            state, label = 'present', 'Present'
            counts['present'] += 1
        elif not work:
            state, label = 'off', 'Day off'
            counts['off'] += 1
        elif leave:
            state, label = 'leave', 'Paid leave' if leave['paid'] else 'Unpaid leave'
            counts['leave'] += 1
        elif day < current:
            state, label = 'absent', 'Absent'
            counts['absent'] += 1
        else:
            state, label = 'scheduled', 'Not checked in' if day == current else 'Working day'
        days.append({
            'date': day,
            'number': date.day,
            'state': state,
            'label': label,
            'pending': pending,
            'punched_at': punches[day]['punched_at'] if day in punches else None,
        })
        date += timedelta(days=1)
    return {'days': days, 'counts': counts, 'offset': first.isoweekday() - 1}


def hr_advance_total(uid, month):
    row = db.one(
        "SELECT COALESCE(SUM(amount),0) amount FROM salary_advances WHERE user_id=%s AND deduction_month=%s AND status='paid'",
        [uid, month],
    )
    return float(row['amount'])


def hr_salary_amounts(base, allowances, deductions, advances):
    net = php_round(base + allowances - deductions - advances, 2)
    if net < 0:
        raise AppError('Deductions and paid advances exceed salary plus allowances.')
    return {'advance_deduction': advances, 'net_salary': net}


def hr_refresh_salary(uid, month):
    report = db.one('SELECT * FROM salary_reports WHERE user_id=%s AND salary_month=%s FOR UPDATE', [uid, month])
    if not report:
        return
    if report['paid_at']:
        raise AppError('This salary month has already been paid. Choose an unpaid month for the advance deduction.')
    amounts = hr_salary_amounts(
        float(report['base_salary']), float(report['allowances']), float(report['deductions']), hr_advance_total(uid, month)
    )
    db.q('UPDATE salary_reports SET advance_deduction=%s,net_salary=%s WHERE id=%s',
         [amounts['advance_deduction'], amounts['net_salary'], report['id']])


HR_ACTIONS = ('salary_default', 'salary_report', 'salary_paid', 'advance_request', 'advance_review',
              'leave_request', 'leave_review', 'workdays')


def hr_action(action, u):
    if action not in HR_ACTIONS:
        return False
    if action == 'workdays':
        require_admin(u)
        days = post().get('working_days', {})
        if not is_array(days) or not len(days) or len(days) > 7:
            raise AppError('Choose at least one working day.')
        for day in days.values():
            if str(day) not in ('1', '2', '3', '4', '5', '6', '7'):
                raise AppError('Invalid working day.')
        unique = sorted({int(day) for day in days.values()})
        db.q("UPDATE hr_settings SET setting_value=%s WHERE setting_key='working_days'", [','.join(str(day) for day in unique)])
        return True
    if action == 'salary_default':
        require_admin(u)
        user_id = to_int(val('user_id'))
        hr_salesman(user_id)
        amount = positive('monthly_salary', True)
        db.q('INSERT INTO employee_salary(user_id,monthly_salary) VALUES (%s,%s) ON DUPLICATE KEY UPDATE monthly_salary=VALUES(monthly_salary)',
             [user_id, amount])
        return True
    if action == 'salary_report':
        require_admin(u)
        user_id = to_int(val('user_id'))
        hr_salesman(user_id)
        month = hr_month(required('salary_month', 7))
        base = positive('base_salary', True)
        allowance = positive('allowances', True)
        deduction = positive('deductions', True)
        notes = val('notes', 3000)
        db.begin()
        hr_lock(user_id)
        existing = db.one('SELECT * FROM salary_reports WHERE user_id=%s AND salary_month=%s FOR UPDATE', [user_id, month])
        if existing and existing['paid_at']:
            raise AppError('Paid salary reports cannot be edited.')
        amounts = hr_salary_amounts(base, allowance, deduction, hr_advance_total(user_id, month))
        db.q(
            'INSERT INTO salary_reports(user_id,salary_month,base_salary,allowances,deductions,advance_deduction,net_salary,notes,updated_by) '
            'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE base_salary=VALUES(base_salary),allowances=VALUES(allowances),'
            'deductions=VALUES(deductions),advance_deduction=VALUES(advance_deduction),net_salary=VALUES(net_salary),notes=VALUES(notes),'
            'updated_by=VALUES(updated_by)',
            [user_id, month, base, allowance, deduction, amounts['advance_deduction'], amounts['net_salary'], notes, u['id']],
        )
        db.commit()
        return True
    if action == 'salary_paid':
        require_admin(u)
        user_id = to_int(val('user_id'))
        hr_salesman(user_id)
        month = hr_month(required('salary_month', 7))
        reference = required('payment_reference', 190)
        if month > php_date('Y-m'):
            raise AppError('Future salary reports cannot be marked paid.')
        db.begin()
        hr_lock(user_id)
        report = db.one('SELECT * FROM salary_reports WHERE user_id=%s AND salary_month=%s FOR UPDATE', [user_id, month])
        if not report or report['paid_at']:
            raise AppError('An unpaid salary report is required.')
        hr_refresh_salary(user_id, month)
        db.q('UPDATE salary_reports SET paid_at=NOW(),payment_reference=%s,updated_by=%s WHERE id=%s', [reference, u['id'], report['id']])
        db.commit()
        return True
    if action == 'advance_request':
        if u['role'] != 'salesman':
            raise AppError('Only salesmen can request salary advances.')
        amount = positive('amount')
        month = hr_month(required('deduction_month', 7))
        if month < php_date('Y-m'):
            raise AppError('Choose the current month or a future deduction month.')
        reason = required('reason', 2000)
        db.begin()
        hr_lock(int(u['id']))
        report = db.one('SELECT paid_at FROM salary_reports WHERE user_id=%s AND salary_month=%s', [u['id'], month])
        if report and report['paid_at']:
            raise AppError('This salary month has already been paid.')
        db.q('INSERT INTO salary_advances(user_id,amount,reason,deduction_month) VALUES (%s,%s,%s,%s)', [u['id'], amount, reason, month])
        db.commit()
        return True
    if action == 'advance_review':
        require_admin(u)
        advance_id = to_int(val('id'))
        before = db.one('SELECT user_id FROM salary_advances WHERE id=%s', [advance_id])
        if not before:
            raise AppError('Advance unavailable.')
        db.begin()
        hr_lock(int(before['user_id']))
        record = db.one('SELECT * FROM salary_advances WHERE id=%s FOR UPDATE', [advance_id])
        status = required('status')
        note = required('review_note', 2000)
        allowed = (record['status'] == 'pending' and status in ('approved', 'rejected')) or \
                  (record['status'] == 'approved' and status in ('paid', 'rejected'))
        if not allowed:
            raise AppError('Invalid advance status change.')
        reference = required('payment_reference', 190) if status == 'paid' else None
        db.q("UPDATE salary_advances SET status=%s,review_note=%s,reviewed_by=%s,paid_at=IF(%s='paid',NOW(),NULL),payment_reference=%s WHERE id=%s",
             [status, note, u['id'], status, reference, advance_id])
        if status == 'paid':
            hr_refresh_salary(int(record['user_id']), record['deduction_month'])
        db.commit()
        return True
    if action == 'leave_request':
        start = hr_date(required('start_date', 10))
        end = hr_date(required('end_date', 10))
        reason = required('reason', 2000)
        if end < start or (to_dt(end) - to_dt(start)).days > 365:
            raise AppError('Choose a leave range of up to 366 days.')
        db.begin()
        hr_lock(int(u['id']))
        if db.one("SELECT id FROM leave_requests WHERE user_id=%s AND status IN ('pending','approved') AND start_date<=%s AND end_date>=%s",
                  [u['id'], end, start]):
            raise AppError('This range overlaps an existing pending or approved leave.')
        if db.one('SELECT id FROM attendance WHERE user_id=%s AND day BETWEEN %s AND %s LIMIT 1', [u['id'], start, end]):
            raise AppError('Leave cannot overlap recorded attendance.')
        db.q('INSERT INTO leave_requests(user_id,start_date,end_date,reason) VALUES (%s,%s,%s,%s)', [u['id'], start, end, reason])
        db.commit()
        return True
    if action == 'leave_review':
        require_admin(u)
        leave_id = to_int(val('id'))
        before = db.one('SELECT user_id FROM leave_requests WHERE id=%s', [leave_id])
        if not before:
            raise AppError('Leave unavailable.')
        db.begin()
        hr_lock(int(before['user_id']))
        record = db.one('SELECT * FROM leave_requests WHERE id=%s FOR UPDATE', [leave_id])
        status = required('status')
        if record['status'] != 'pending' or status not in ('approved', 'rejected'):
            raise AppError('Only pending leave can be reviewed.')
        if status == 'approved' and db.one('SELECT id FROM attendance WHERE user_id=%s AND day BETWEEN %s AND %s LIMIT 1',
                                           [record['user_id'], record['start_date'], record['end_date']]):
            raise AppError('Leave overlaps recorded attendance.')
        paid = 1 if status == 'approved' and val('paid') == '1' else 0
        db.q('UPDATE leave_requests SET status=%s,paid=%s,review_note=%s,reviewed_by=%s WHERE id=%s',
             [status, paid, required('review_note', 2000), u['id'], leave_id])
        db.commit()
        return True
    return False
