import threading

from . import config, db

SCHEMA_FILE = config.BASE_DIR / 'schema.sql'
_lock = threading.Lock()
_ready = {'done': False}


def apply_schema():
    sql = SCHEMA_FILE.read_text(encoding='utf-8')
    for statement in sql.split(';'):
        statement = statement.strip()
        if not statement:
            continue
        if statement.startswith('INSERT INTO products'):
            if int(db.one('SELECT COUNT(*) n FROM products')['n']) == 0:
                db.q(statement)
        else:
            db.q(statement)


def ensure_role_schema():
    role = db.one("SHOW COLUMNS FROM users LIKE 'role'")
    if role and "'fabricator'" not in str(role['Type']):
        db.q("ALTER TABLE users MODIFY role ENUM('admin','finance','salesman','freelancer','fabricator') NOT NULL DEFAULT 'salesman'")
    source = db.one("SHOW COLUMNS FROM orders LIKE 'source'")
    if source and "'fabricator'" not in str(source['Type']):
        db.q("ALTER TABLE orders MODIFY source ENUM('salesman','admin','ecommerce','freelancer','fabricator') NOT NULL")
    if db.one("SHOW TABLES LIKE 'leads'") and not db.one("SHOW COLUMNS FROM leads LIKE 'erp_lead'"):
        db.q("ALTER TABLE leads ADD COLUMN erp_lead VARCHAR(140) NULL")


def hr_ensure():
    ensure_role_schema()
    if db.one("SHOW TABLES LIKE 'hr_settings'") and db.one("SELECT setting_value FROM hr_settings WHERE setting_key='schema_version'"):
        return
    apply_schema()


def wf_ensure():
    if db.one("SHOW TABLES LIKE 'wf_meta'") and db.one("SELECT meta_value FROM wf_meta WHERE meta_key='schema_version'"):
        return
    apply_schema()


def qt_ensure():
    if db.one("SELECT meta_value FROM wf_meta WHERE meta_key='quotation_ui_v2'"):
        return
    columns = {
        'customer_details': 'TEXT NULL',
        'discount_type': "VARCHAR(10) NOT NULL DEFAULT 'amount'",
        'discount_value': 'DECIMAL(12,2) NOT NULL DEFAULT 0',
        'template_id': 'INT NULL',
    }
    for column, definition in columns.items():
        if not db.one("SHOW COLUMNS FROM wf_quotations LIKE '%s'" % column):
            db.q('ALTER TABLE wf_quotations ADD COLUMN `%s` %s' % (column, definition))
    db.q("UPDATE wf_quotations SET discount_value=discount WHERE discount_type='amount' AND discount_value=0 AND discount<>0")
    db.q('ALTER TABLE wf_quotation_items MODIFY measurement_id INT NULL, MODIFY drawing_id INT NULL')
    db.q(
        'CREATE TABLE IF NOT EXISTS qt_templates (id INT AUTO_INCREMENT PRIMARY KEY, title VARCHAR(150) NOT NULL, '
        'terms TEXT NOT NULL, active BOOLEAN NOT NULL DEFAULT 1, created_by INT NOT NULL, '
        'FOREIGN KEY(created_by) REFERENCES users(id))'
    )
    db.q("INSERT IGNORE INTO wf_meta(meta_key,meta_value) VALUES ('quotation_ui_v2','1')")


def survey_ensure():
    if db.one("SELECT meta_value FROM wf_meta WHERE meta_key='survey_sides_v1'"):
        return
    db.q(
        'CREATE TABLE IF NOT EXISTS door_handle_brands (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(150) NOT NULL, '
        'company VARCHAR(190) NULL, details TEXT NULL, active BOOLEAN NOT NULL DEFAULT 1, created_by INT NOT NULL, '
        'created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(created_by) REFERENCES users(id))'
    )
    columns = {
        'side_top': 'VARCHAR(40) NULL',
        'side_bottom': 'VARCHAR(40) NULL',
        'side_left': 'VARCHAR(40) NULL',
        'side_right': 'VARCHAR(40) NULL',
        'inner_detail': 'VARCHAR(80) NULL',
        'handle_brand_id': 'INT NULL',
        'handle_brand': 'VARCHAR(150) NULL',
    }
    for column, definition in columns.items():
        if not db.one("SHOW COLUMNS FROM wf_measurements LIKE '%s'" % column):
            db.q('ALTER TABLE wf_measurements ADD COLUMN `%s` %s' % (column, definition))
    db.q("INSERT IGNORE INTO wf_meta(meta_key,meta_value) VALUES ('survey_sides_v1','1')")


def brand_image_ensure():
    if db.one("SELECT meta_value FROM wf_meta WHERE meta_key='brand_image_v1'"):
        return
    if not db.one("SHOW COLUMNS FROM door_handle_brands LIKE 'image'"):
        db.q('ALTER TABLE door_handle_brands ADD COLUMN image VARCHAR(80) NULL')
    db.q("INSERT IGNORE INTO wf_meta(meta_key,meta_value) VALUES ('brand_image_v1','1')")


def lead_ensure():
    if db.one("SELECT meta_value FROM wf_meta WHERE meta_key='lead_ui_v2'"):
        return
    columns = {
        'lead_no': 'VARCHAR(40) NULL',
        'lead_date': 'DATE NULL',
        'customer_type': "VARCHAR(15) NOT NULL DEFAULT 'new'",
        'address2': 'VARCHAR(500) NULL',
        'postal_code': 'VARCHAR(20) NULL',
        'post_office': 'VARCHAR(190) NULL',
        'state': 'VARCHAR(100) NULL',
        'district': 'VARCHAR(100) NULL',
        'contact_date': 'DATE NULL',
        'stage': "VARCHAR(30) NOT NULL DEFAULT 'Lead'",
        'status_remark': 'TEXT NULL',
    }
    for column, definition in columns.items():
        if not db.one("SHOW COLUMNS FROM leads LIKE '%s'" % column):
            db.q('ALTER TABLE leads ADD COLUMN `%s` %s' % (column, definition))
    db.q('UPDATE leads SET lead_date=DATE(COALESCE(created_at,NOW())) WHERE lead_date IS NULL')
    db.q("UPDATE leads SET stage=CASE status WHEN 'qualified' THEN 'Oppurtunity' WHEN 'converted' THEN 'Quotation' WHEN 'lost' THEN 'Lost Quotation' ELSE 'Lead' END WHERE stage='Lead'")
    db.q("UPDATE leads SET lead_no=CONCAT(LPAD(MOD(YEAR(lead_date)-(MONTH(lead_date)<4),100),2,'0'),'-',"
         "LPAD(MOD(YEAR(lead_date)-(MONTH(lead_date)<4)+1,100),2,'0'),'-LEAD-',LPAD(id,4,'0')) WHERE lead_no IS NULL")
    db.q("INSERT IGNORE INTO wf_meta(meta_key,meta_value) VALUES ('lead_ui_v2','1')")


def team_ensure():
    if not db.one("SHOW COLUMNS FROM users LIKE 'employee_id'"):
        db.q('ALTER TABLE users ADD COLUMN employee_id VARCHAR(60) NULL')


def commission_ensure():
    if db.one("SELECT meta_value FROM wf_meta WHERE meta_key='commission_schemes_v1'"):
        return
    db.q(
        'CREATE TABLE IF NOT EXISTS commission_schemes (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(150) NOT NULL, '
        'percentage DECIMAL(5,2) NOT NULL DEFAULT 0.00, created_by INT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, '
        'UNIQUE KEY uq_commission_scheme_name (name))'
    )
    if not db.one("SHOW COLUMNS FROM users LIKE 'commission_scheme_id'"):
        db.q('ALTER TABLE users ADD COLUMN commission_scheme_id INT NULL')
    for row in db.rows("SELECT DISTINCT commission_rate FROM users WHERE role IN ('salesman','freelancer') AND commission_rate>0"):
        rate = row['commission_rate']
        label = ('%.2f' % float(rate)).rstrip('0').rstrip('.') + '% Commission'
        db.q('INSERT IGNORE INTO commission_schemes(name,percentage) VALUES (%s,%s)', [label, rate])
        scheme = db.one('SELECT id FROM commission_schemes WHERE name=%s', [label])
        db.q("UPDATE users SET commission_scheme_id=%s WHERE role IN ('salesman','freelancer') AND commission_rate=%s AND commission_scheme_id IS NULL",
             [scheme['id'], rate])
    db.q("INSERT IGNORE INTO wf_meta(meta_key,meta_value) VALUES ('commission_schemes_v1','1')")


def avatar_ensure():
    if not db.one("SHOW COLUMNS FROM users LIKE 'avatar'"):
        db.q('ALTER TABLE users ADD COLUMN avatar VARCHAR(80) NULL')
    if not db.one("SHOW COLUMNS FROM users LIKE 'avatar_src'"):
        db.q('ALTER TABLE users ADD COLUMN avatar_src VARCHAR(255) NULL')


def survey_view_ensure():
    if not db.one("SHOW COLUMNS FROM wf_measurements LIKE 'frame_mode'"):
        db.q("ALTER TABLE wf_measurements ADD COLUMN frame_mode VARCHAR(10) NOT NULL DEFAULT 'frame'")
    if not db.one("SHOW COLUMNS FROM wf_measurements LIKE 'display_unit'"):
        db.q("ALTER TABLE wf_measurements ADD COLUMN display_unit VARCHAR(5) NOT NULL DEFAULT 'cm'")


def deletion_ensure():
    from .deletion import ensure_log_table
    ensure_log_table()


def ensure_all():

    if _ready['done']:
        return
    with _lock:
        if _ready['done']:
            return
        hr_ensure()
        wf_ensure()
        qt_ensure()
        survey_ensure()
        brand_image_ensure()
        lead_ensure()
        team_ensure()
        commission_ensure()
        avatar_ensure()
        survey_view_ensure()
        deletion_ensure()

        _ready['done'] = True
