import logging

import requests

from . import config, db

log = logging.getLogger(__name__)

TYPE_BY_ROLE = {'freelancer': 'Freelancer', 'salesman': 'Company', 'fabricator': 'Fabricator'}
STATUS_BY_STAGE = {
    'Lead': 'Lead', 'Oppurtunity': 'Opportunity', 'Oppurtunity 50%': 'Opportunity', 'Oppurtunity 75%': 'Opportunity',
    'Oppurtunity 90%': 'Opportunity', 'Quotation': 'Quotation', 'Do not Contact': 'Do Not Contact', 'Lost Quotation': 'Lost Quotation',
}


def _text(value):
    return '' if value is None else str(value)


def lead_payload(lead_id):
    row = db.one('SELECT l.*,u.name salesman_name,u.username salesman_username,u.role salesman_role FROM leads l JOIN users u ON u.id=l.salesman_id WHERE l.id=%s',
                 [lead_id])
    if not row:
        return None
    from .leads import lead_number
    payload = {
        'doctype': 'Lead',
        'first_name': _text(row['name']),
        'mobile_no': _text(row['phone']),
        'status': STATUS_BY_STAGE.get(row.get('stage'), 'Lead'),
        'country': 'India',
        'state': _text(row['state']),
        'city': _text(row['district']),
        'zivoc_lead_id': str(int(row['id'])),
        'zivoc_lead_no': lead_number(row),
        'customer_type': _text(row['customer_type']),
        'zivoc_stage': _text(row['stage']),
        'lead_date': _text(row['lead_date'])[:10] or None,
        'contact_date': _text(row['contact_date'])[:10] or None,
        'address_line_1': _text(row['address']),
        'address_line_2': _text(row['address2']),
        'postal_code': _text(row['postal_code']),
        'post_office': _text(row['post_office']),
        'district': _text(row['district']),
        'zivoc_salesman': _text(row['salesman_name']),
        'zivoc_salesman_username': _text(row['salesman_username']),
        'lead_remark': _text(row['notes']),
        'status_remark': _text(row['status_remark']),
    }
    lead_type = TYPE_BY_ROLE.get(row['salesman_role'])
    if lead_type:
        payload['type'] = lead_type
    return {key: value for key, value in payload.items() if value not in (None, '')}


def push_lead(lead_id):
    if not config.ERP_TOKEN or not config.ERP_BASE_URL:
        return False
    try:
        payload = lead_payload(lead_id)
        if not payload:
            return False
        response = requests.post(
            config.ERP_BASE_URL + '/api/resource/Lead', json=payload,
            headers={'Authorization': 'token ' + config.ERP_TOKEN, 'Accept': 'application/json'}, timeout=(5, 20))
        if response.status_code not in (200, 201):
            log.error('ERP lead push failed for lead %s: HTTP %s %s', lead_id, response.status_code, response.text[:500])
            return False
        name = (response.json().get('data') or {}).get('name')
        if name:
            db.q('UPDATE leads SET erp_lead=%s WHERE id=%s', [name, lead_id])
            db.commit()
        return True
    except Exception:
        log.exception('ERP lead push failed for lead %s', lead_id)
        return False
