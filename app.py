import os
import json
import csv
import io
import sqlite3
import random
import hashlib
import smtplib
import pandas as pd
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, abort, send_file, session
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

load_dotenv()

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data.sqlite3"
CONFIG_PATH = BASE_DIR / "config.json"
UPLOADS_DIR = BASE_DIR / "uploads"
ASSETS_DIR = BASE_DIR / "assets"

with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    CFG = json.load(f)

APP_TITLE = os.getenv("APP_TITLE", "Simple Test Platform")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "changeme")

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ------------------------- DB helpers -------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS respondents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            name TEXT,
            student_id TEXT,
            extra_json TEXT
        );
        CREATE TABLE IF NOT EXISTS otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            code_hash TEXT,
            expires_at TEXT,
            send_count INTEGER DEFAULT 0,
            last_sent_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE,
            name TEXT,
            attempts_limit INTEGER,
            config_json TEXT
        );
        CREATE TABLE IF NOT EXISTS question_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER,
            set_type TEXT,  -- 'tutorial' or 'main'
            imported_at TEXT,
            source_file TEXT
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_id INTEGER,
            question_id TEXT,
            text TEXT,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct_option TEXT
        );
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER,
            respondent_id INTEGER,
            attempt_no INTEGER,
            score REAL,
            total_points REAL,
            started_at TEXT,
            finished_at TEXT,
            violations_count INTEGER DEFAULT 0,
            details_json TEXT
        );
        CREATE TABLE IF NOT EXISTS randomization_maps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER,
            respondent_id INTEGER,
            attempt_no INTEGER,
            q_order_json TEXT,
            options_order_json TEXT
        );
        """
    )
    # Seed single test from CFG if not exists
    slug = CFG['test']['slug']
    name = CFG['test']['name']
    attempts_limit = CFG['test']['attempts_limit']
    exists = conn.execute("SELECT id FROM tests WHERE slug=?", (slug,)).fetchone()
    if not exists:
        conn.execute("INSERT INTO tests (slug, name, attempts_limit, config_json) VALUES (?,?,?,?)",
                     (slug, name, attempts_limit, json.dumps(CFG)))
    conn.close()

# ------------------------- Email -------------------------

def send_email_code(email: str, code: str):
    provider = CFG.get('email', {}).get('provider', 'smtp')
    subject = f"Your login code for {CFG['test']['name']}"
    body = f"Your one-time code is: {code}\nIt expires in 10 minutes."
    if provider == 'smtp':
        smtp_cfg = CFG['email']['smtp']
        if not smtp_cfg.get('host'):
            print('[EMAIL] SMTP not configured. Code for', email, 'is', code)
            return True
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = formataddr(('Test Platform', smtp_cfg['from']))
        msg['To'] = email
        try:
            server = smtplib.SMTP(smtp_cfg['host'], smtp_cfg['port'])
            if smtp_cfg.get('use_tls', True):
                server.starttls()
            if smtp_cfg.get('username'):
                server.login(smtp_cfg['username'], smtp_cfg['password'])
            server.sendmail(smtp_cfg['from'], [email], msg.as_string())
            server.quit()
            return True
        except Exception as e:
            print('[EMAIL] SMTP send failed:', e)
            return False
    else:
        # sendgrid/ses placeholders
        print('[EMAIL] Provider', provider, 'not implemented; code for', email, 'is', code)
        return True

# ------------------------- Utility -------------------------

def mmss_to_seconds(mmss: str) -> int:
    mm, ss = mmss.split(':')
    return int(mm) * 60 + int(ss)


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def grade_from_percent(pct: float):
    for rule in CFG['branding']['certificate']['grade_thresholds']:
        if pct >= rule['min_percent']:
            return rule['grade'], rule['desc']
    return 'F', 'Needs Improvement'

# ------------------------- Routes -------------------------

@app.get('/')
def root():
    return redirect(url_for('login'))

@app.get('/login')
def login():
    return render_template('login.html',
        app_title=APP_TITLE,
        test_name=CFG['test']['name'],
        logo_path=CFG['branding']['logo_path'],
        instructions=CFG['test']['instructions_html'],
        consent_text=CFG['test']['consent_text'],
        access_code_required=CFG['test']['access_code_required'])

@app.post('/request-otp')
def request_otp():
    name = request.form.get('name','').strip()
    student_id = request.form.get('student_id','').strip()
    email = request.form.get('email','').strip().lower()
    consent = request.form.get('consent','') == 'on'
    access_code = request.form.get('access_code','').strip()
    if CFG['test']['access_code_required'] and access_code != CFG['test']['access_code']:
        return 'Invalid access code.', 400
    if not (name and email and consent):
        return 'Name, email and consent are required.', 400

    # rate limit: 3 sends/hour per email
    conn = get_db()
    now = datetime.now(timezone.utc)
    row = conn.execute("SELECT id, send_count, last_sent_at FROM otp_codes WHERE email=?", (email,)).fetchone()
    if row:
        send_count = row['send_count'] or 0
        last_sent = datetime.fromisoformat(row['last_sent_at']) if row['last_sent_at'] else now - timedelta(hours=1)
        if send_count >= 10 and (now - last_sent) < timedelta(hours=1):
            conn.close()
            return 'Too many requests. Try later.', 429
    # generate code
    code = f"{random.randint(0,999999):06d}"
    ok = send_email_code(email, code)
    expires = (now + timedelta(minutes=10)).isoformat()
    h = hash_code(code)
    if row:
        conn.execute("UPDATE otp_codes SET code_hash=?, expires_at=?, send_count=?, last_sent_at=? WHERE id=?",
                     (h, expires, (row['send_count'] or 0) + 1, now.isoformat(), row['id']))
    else:
        conn.execute("INSERT INTO otp_codes (email, code_hash, expires_at, send_count, last_sent_at) VALUES (?,?,?,?,?)",
                     (email, h, expires, 1, now.isoformat()))
    # upsert respondent
    r = conn.execute("SELECT id FROM respondents WHERE email=?", (email,)).fetchone()
    if r:
        conn.execute("UPDATE respondents SET name=?, student_id=? WHERE id=?", (name, student_id, r['id']))
        respondent_id = r['id']
    else:
        conn.execute("INSERT INTO respondents (email, name, student_id, extra_json) VALUES (?,?,?,?)",
                     (email, name, student_id, json.dumps({})))
        respondent_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
    conn.close()
    session['email'] = email
    session['respondent_id'] = respondent_id
    return render_template('verify.html', app_title=APP_TITLE)

@app.post('/verify-otp')
def verify_otp():
    email = session.get('email')
    code = request.form.get('otp','').strip()
    if not (email and code):
        return 'Missing data.', 400
    conn = get_db()
    row = conn.execute("SELECT code_hash, expires_at FROM otp_codes WHERE email=?", (email,)).fetchone()
    if not row:
        conn.close(); return 'Code not found.', 400
    if datetime.now(timezone.utc) > datetime.fromisoformat(row['expires_at']):
        conn.close(); return 'Code expired.', 400
    if hash_code(code) != row['code_hash']:
        conn.close(); return 'Invalid code.', 400

    # attempts check
    test = conn.execute("SELECT id, attempts_limit FROM tests WHERE slug=?", (CFG['test']['slug'],)).fetchone()
    respondent_id = session.get('respondent_id')
    count = conn.execute("SELECT COUNT(*) AS c FROM submissions WHERE test_id=? AND respondent_id=?",
                         (test['id'], respondent_id)).fetchone()['c']
    if count >= (test['attempts_limit'] or 1):
        conn.close(); return 'Attempts limit reached.', 403

    # prepare tutorial set
    set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type='tutorial'", (test['id'],)).fetchone()
    if not set_row:
        # import default tutorial from sample CSV
        import_file_to_set(conn, test['id'], 'tutorial', UPLOADS_DIR / 'tutorial_sample.csv')
        set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type='tutorial'", (test['id'],)).fetchone()

    tutorial_questions = load_questions_for_set(conn, set_row['id'])
    conn.close()
    session['test_id'] = test['id']
    session['attempt_no'] = count + 1
    # timer
    per_sec = mmss_to_seconds(CFG['test']['per_question_time_mmss'])
    return render_template('tutorial.html', app_title=APP_TITLE, per_question_seconds=per_sec, questions=tutorial_questions)

# Helpers for import & load

def import_file_to_set(conn, test_id: int, set_type: str, path: Path):
    imported_at = datetime.now(timezone.utc).isoformat()
    conn.execute("INSERT INTO question_sets (test_id, set_type, imported_at, source_file) VALUES (?,?,?,?)",
                 (test_id, set_type, imported_at, str(path)))
    set_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
    # Read CSV/XLSX
    if str(path).lower().endswith('.xlsx'):
        df = pd.read_excel(path, engine='openpyxl')
    else:
        df = pd.read_csv(path)
    for _, row in df.iterrows():
        conn.execute("INSERT INTO questions (set_id, question_id, text, option_a, option_b, option_c, option_d, correct_option) VALUES (?,?,?,?,?,?,?,?)",
                     (set_id, str(row['question_id']), str(row['question_text']),
                      str(row.get('option_a','') or ''), str(row.get('option_b','') or ''),
                      str(row.get('option_c','') or ''), str(row.get('option_d','') or ''),
                      str(row['correct_option']).strip().lower()))
    return set_id


def load_questions_for_set(conn, set_id: int):
    rows = conn.execute("SELECT question_id, text, option_a, option_b, option_c, option_d, correct_option FROM questions WHERE set_id=? ORDER BY id ASC", (set_id,)).fetchall()
    qlist = []
    for r in rows:
        q = {
            'id': r['question_id'],
            'text': r['text'],
            'options': {
                'a': r['option_a'],
                'b': r['option_b'],
                'c': r['option_c'],
                'd': r['option_d']
            },
            'correct': r['correct_option']
        }
        qlist.append(q)
    return qlist

@app.post('/start-real-test')
def start_real_test():
    # Load main set; create randomization map stable per respondent
    test_id = session.get('test_id')
    respondent_id = session.get('respondent_id')
    attempt_no = session.get('attempt_no')
    if not (test_id and respondent_id and attempt_no):
        return redirect(url_for('login'))
    conn = get_db()
    set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type='main'", (test_id,)).fetchone()
    if not set_row:
        import_file_to_set(conn, test_id, 'main', UPLOADS_DIR / 'main_sample.csv')
        set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type='main'", (test_id,)).fetchone()
    questions = load_questions_for_set(conn, set_row['id'])
    # Build stable randomization
    q_ids = [q['id'] for q in questions]
    q_order = q_ids[:]
    if CFG['test']['randomize_questions']:
        random.shuffle(q_order)
    options_order = {}
    if CFG['test']['randomize_options']:
        for q in questions:
            opts = ['a','b','c','d']
            random.shuffle(opts)
            options_order[q['id']] = opts
    else:
        for q in questions:
            options_order[q['id']] = ['a','b','c','d']
    # persist map
    conn.execute("INSERT INTO randomization_maps (test_id, respondent_id, attempt_no, q_order_json, options_order_json) VALUES (?,?,?,?,?)",
                 (test_id, respondent_id, attempt_no, json.dumps(q_order), json.dumps(options_order)))
    conn.close()
    session['q_order'] = q_order
    session['options_order'] = options_order
    # Render in single-question flow
    per_sec = mmss_to_seconds(CFG['test']['per_question_time_mmss'])
    max_leaves = CFG['test']['anti_cheat']['max_tab_leaves']
    action = CFG['test']['anti_cheat']['action']

    # materialize questions in ordered form with shuffled options
    ordered = []
    mapping = {q['id']: q for q in questions}
    for qid in q_order:
        q = mapping[qid]
        opts_keys = options_order[qid]
        opts_texts = [q['options'][k] for k in opts_keys]
        ordered.append({'id': qid, 'text': q['text'], 'options': opts_texts})

    return render_template('quiz.html', app_title=APP_TITLE, logo_path=CFG['branding']['logo_path'], test_name=CFG['test']['name'],
                           per_question_seconds=per_sec, max_tab_leaves=max_leaves, violation_action=action,
                           questions=ordered)

@app.get('/blocked')
def blocked():
    return render_template('blocked.html', app_title=APP_TITLE)

@app.post('/'+CFG['test']['slug']+'/submit')
def submit_quiz():
    test_id = session.get('test_id')
    respondent_id = session.get('respondent_id')
    attempt_no = session.get('attempt_no')
    q_order = session.get('q_order')
    options_order = session.get('options_order')
    if not all([test_id, respondent_id, attempt_no, q_order, options_order]):
        return redirect(url_for('login'))

    conn = get_db()
    set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type='main'", (test_id,)).fetchone()
    questions = load_questions_for_set(conn, set_row['id'])
    mapping = {q['id']: q for q in questions}

    score = 0.0
    total_points = float(len(q_order))  # 1 point each
    details = []
    for qid in q_order:
        q = mapping[qid]
        # Determine given answer: request.form has value texts, compare to option keys via options_order
        opts_keys = options_order[qid]
        opts_texts = [q['options'][k] for k in opts_keys]
        given_text = request.form.get(qid, '').strip()
        # Map back to key
        given_key = None
        for i, t in enumerate(opts_texts):
            if t == given_text:
                given_key = opts_keys[i]
                break
        correct = (given_key == q['correct'])
        if correct:
            score += 1
        details.append({
            'qid': qid,
            'text': q['text'],
            'given_text': given_text,
            'given_key': given_key,
            'correct_key': q['correct'],
            'correct': correct
        })

    violations = int(request.form.get('violations','0') or 0)
    now = datetime.now(timezone.utc)
    conn.execute("INSERT INTO submissions (test_id, respondent_id, attempt_no, score, total_points, started_at, finished_at, violations_count, details_json) VALUES (?,?,?,?,?,?,?,?,?)",
                 (test_id, respondent_id, attempt_no, score, total_points, session.get('started_at', now.isoformat()), now.isoformat(), violations, json.dumps(details)))
    sub_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
    conn.close()

    percent = (score / total_points) * 100.0
    grade, desc = grade_from_percent(percent)
    # Generate certificate PDF
    cert_path = BASE_DIR / f"certificate_{sub_id}.pdf"
    generate_certificate(cert_path, respondent_id, sub_id, score, total_points, percent, grade, desc)
    session['last_submission_id'] = sub_id

    end_msg = CFG['test']['end_message_html']
    redirect_url = CFG['test']['end_redirect_url']
    return render_template('thankyou.html', app_title=APP_TITLE, end_message=end_msg, redirect_url=redirect_url, cert_ready=True, submission_id=sub_id)

# Certificate generation

def respondent_name(conn, respondent_id):
    r = conn.execute("SELECT name FROM respondents WHERE id=?", (respondent_id,)).fetchone()
    return r['name'] if r else 'Respondent'


def generate_certificate(path: Path, respondent_id: int, submission_id: int, score: float, total: float, percent: float, grade: str, desc: str):
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    # Logo
    logo_path = ASSETS_DIR / Path(CFG['branding']['logo_path']).name
    try:
        if logo_path.exists():
            logo = ImageReader(str(logo_path))
            c.drawImage(logo, 20*mm, height - 40*mm, width=40*mm, preserveAspectRatio=True, mask='auto')
    except Exception:
        pass
    # Title & subtitle
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, height - 30*mm, CFG['branding']['certificate']['subtitle'])
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height - 38*mm, CFG['test']['name'])
    # Name
    conn = get_db()
    name = respondent_name(conn, respondent_id)
    conn.close()
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, height - 55*mm, name)
    # Paragraphs
    text = c.beginText(25*mm, height - 75*mm)
    text.setFont("Helvetica", 11)
    text.textLines(CFG['branding']['certificate']['paragraph1'] + "\n\n" + CFG['branding']['certificate']['paragraph2'])
    c.drawText(text)
    # Scores
    c.setFont("Helvetica", 12)
    c.drawString(25*mm, height - 110*mm, f"Points score: {int(score)} / {int(total)}")
    c.drawString(25*mm, height - 120*mm, f"Percentage score: {percent:.2f}%")
    c.drawString(25*mm, height - 130*mm, f"Grade: {grade} ({desc})")
    # Signatures
    try:
        left_sig = ASSETS_DIR / Path(CFG['branding']['certificate']['signature_left_path']).name
        right_sig = ASSETS_DIR / Path(CFG['branding']['certificate']['signature_right_path']).name
        if left_sig.exists():
            c.drawImage(ImageReader(str(left_sig)), 25*mm, 25*mm, width=50*mm, preserveAspectRatio=True, mask='auto')
        if right_sig.exists():
            c.drawImage(ImageReader(str(right_sig)), width - 75*mm, 25*mm, width=50*mm, preserveAspectRatio=True, mask='auto')
    except Exception:
        pass
    # Footnote
    c.setFont("Helvetica", 9)
    c.drawCentredString(width/2, 15*mm, CFG['branding']['certificate']['footnote'])
    c.showPage()
    c.save()

@app.get('/download/certificate/<int:submission_id>')
def download_certificate(submission_id):
    path = BASE_DIR / f"certificate_{submission_id}.pdf"
    if not path.exists():
        abort(404)
    return send_file(str(path), as_attachment=True, download_name=f"certificate_{submission_id}.pdf")

# Admin
@app.get('/admin')
def admin_index():
    token = request.args.get('token','')
    if token != ADMIN_TOKEN: abort(403)
    return render_template('admin.html', app_title=APP_TITLE, token=token)

@app.post('/admin/upload/<set_type>')
def admin_upload(set_type):
    token = request.args.get('token','')
    if token != ADMIN_TOKEN: abort(403)
    f = request.files.get('file')
    if not f: return 'No file', 400
    path = UPLOADS_DIR / f"{set_type}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{f.filename}"
    f.save(str(path))
    conn = get_db()
    test = conn.execute("SELECT id FROM tests WHERE slug=?", (CFG['test']['slug'],)).fetchone()
    import_file_to_set(conn, test['id'], set_type, path)
    conn.close()
    return redirect(url_for('admin_index', token=token))

@app.get('/admin/export')
def export_csv():
    token = request.args.get('token','')
    if token != ADMIN_TOKEN: abort(403)
    conn = get_db()
    rows = conn.execute(
        "SELECT s.id, r.name, r.student_id, r.email, s.score, s.total_points, s.violations_count, s.finished_at FROM submissions s JOIN respondents r ON s.respondent_id=r.id ORDER BY s.finished_at ASC"
    ).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["submission_id","name","student_id","email","score","total_points","violations","finished_at"])
    for r in rows:
        writer.writerow([r['id'], r['name'], r['student_id'], r['email'], r['score'], r['total_points'], r['violations_count'], r['finished_at']])
    output.seek(0)
    filename = f"{CFG['test']['slug']}_submissions_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
    return send_file(io.BytesIO(output.read().encode('utf-8-sig')), as_attachment=True, download_name=filename, mimetype='text/csv')

@app.get('/admin/export.xlsx')
def export_excel():
    token = request.args.get('token','')
    if token != ADMIN_TOKEN: abort(403)
    conn = get_db()
    rows = conn.execute(
        "SELECT s.id, r.name, r.student_id, r.email, s.score, s.total_points, s.violations_count, s.finished_at, s.details_json FROM submissions s JOIN respondents r ON s.respondent_id=r.id ORDER BY s.finished_at ASC"
    ).fetchall()
    conn.close()
    summary = [{
        'submission_id': r['id'], 'name': r['name'], 'student_id': r['student_id'], 'email': r['email'],
        'score': r['score'], 'total_points': r['total_points'], 'violations': r['violations_count'], 'finished_at': r['finished_at']
    } for r in rows]
    answers = []
    for r in rows:
        try:
            det = json.loads(r['details_json'])
        except Exception:
            det = []
        for a in det:
            answers.append({
                'submission_id': r['id'], 'question_id': a.get('qid'), 'question': a.get('text'),
                'given_key': a.get('given_key'), 'given_text': a.get('given_text'), 'correct_key': a.get('correct_key'), 'correct': a.get('correct')
            })
    df_summary = pd.DataFrame(summary)
    df_answers = pd.DataFrame(answers)
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as w:
        df_summary.to_excel(w, index=False, sheet_name='Submissions')
        if not df_answers.empty:
            df_answers.to_excel(w, index=False, sheet_name='Answers')
        meta = pd.DataFrame({'key':['test_slug','generated_at'],'value':[CFG['test']['slug'], datetime.now(timezone.utc).isoformat()]})
        meta.to_excel(w, index=False, sheet_name='Meta')
    output.seek(0)
    filename = f"{CFG['test']['slug']}_submissions_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# Map old URL for submit endpoint
@app.post('/quiz/submit')
def legacy_submit():
    return submit_quiz()

# Initialize
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
