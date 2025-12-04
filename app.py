import os
import json
import csv
import io
import sqlite3
import random
import hashlib
import smtplib
import string
import pandas as pd
import re
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path
import shutil
import urllib.request

from flask import Flask, render_template, request, redirect, url_for, abort, send_file, session, jsonify
from dotenv import load_dotenv
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

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
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # Default admin password

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ------------------------- DB helpers -------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


# Helpers for image saving/normalization
def ensure_image_saved(image_url: str) -> str:
    """Ensure the provided image_url is available under `static/assets/question_images/`.
    Returns a path relative to `static/` (e.g. `assets/question_images/xxx.png`) or the original value on failure.
    """
    image_url = (str(image_url or '')).strip()
    if not image_url:
        return ''

    static_img_dir = BASE_DIR / 'static' / 'assets' / 'question_images'
    static_img_dir.mkdir(parents=True, exist_ok=True)

    # If already a relative static assets path, normalize
    if image_url.startswith('assets/'):
        return image_url
    if image_url.startswith('static/'):
        return image_url[len('static/'):]  # strip leading static/

    # Remote URL: try download
    if image_url.startswith('http://') or image_url.startswith('https://'):
        try:
            ext = os.path.splitext(image_url)[1] or '.png'
            fname = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}{ext}"
            dest = static_img_dir / fname
            urllib.request.urlretrieve(image_url, dest)
            return f"assets/question_images/{fname}"
        except Exception:
            return image_url

    # Local file: check common locations (uploads, project root, static)
    candidates = [UPLOADS_DIR / image_url, BASE_DIR / image_url, BASE_DIR / 'static' / image_url]
    for c in candidates:
        try:
            if c.exists():
                fname = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}_{Path(c).name}"
                dest = static_img_dir / fname
                shutil.copy(str(c), str(dest))
                return f"assets/question_images/{fname}"
        except Exception:
            continue

    return image_url


def init_db():
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS student_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password_hash TEXT,
            name TEXT,
            student_id TEXT,
            level TEXT DEFAULT 'NOVAS',
            status TEXT DEFAULT 'active',
            created_at TEXT,
            expires_at TEXT
        );
        CREATE TABLE IF NOT EXISTS quiz_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER,
            student_id INTEGER,
            session_token TEXT UNIQUE,
            start_time TEXT,
            expiry_time TEXT,
            status TEXT DEFAULT 'active',
            quiz_start_confirmed INTEGER DEFAULT 0
        );
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
            slug TEXT,
            level TEXT,
            name TEXT,
            attempts_limit INTEGER,
            start_time TEXT,
            end_time TEXT,
            status TEXT DEFAULT 'inactive',
            config_json TEXT,
            UNIQUE(slug, level)
        );
        CREATE TABLE IF NOT EXISTS question_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER,
            set_type TEXT,
            imported_at TEXT,
            source_file TEXT
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            set_id INTEGER,
            question_id TEXT,
            text TEXT,
            image_url TEXT,
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
            violation_reason TEXT,
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
    # Seed tests for all levels from CFG if not exists
    slug = CFG['test']['slug']
    levels = ['NOVAS', 'VOYAGERS', 'TITANS', 'LEGENDS']
    level_names = {
        'NOVAS': 'Smart Quest - Year 3-4 (Beginner)',
        'VOYAGERS': 'Smart Quest - Year 5-6 (Intermediate)',
        'TITANS': 'Master Quest - Year 7-8 (Advanced)',
        'LEGENDS': 'Master Quest - Year 9-10 (Master)'
    }
    
    for level in levels:
        exists = conn.execute("SELECT id FROM tests WHERE slug=? AND level=?", (slug, level)).fetchone()
        if not exists:
            name = level_names.get(level, f'{slug} - {level}')
            attempts_limit = CFG['test'].get('attempts_limit', 1)
            conn.execute("INSERT INTO tests (slug, level, name, attempts_limit, config_json, status) VALUES (?,?,?,?,?,?)",
                         (slug, level, name, attempts_limit, json.dumps(CFG), 'inactive'))
    
    # Create default admin if not exists
    admin_exists = conn.execute("SELECT id FROM admin_users WHERE username='admin'").fetchone()
    if not admin_exists:
        admin_pass_hash = hash_password("admin321")
        conn.execute("INSERT INTO admin_users (username, password_hash, created_at) VALUES (?,?,?)",
                     ("admin", admin_pass_hash, datetime.now(timezone.utc).isoformat()))
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

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def verify_password(password: str, hash: str) -> bool:
    return hash_password(password) == hash


def generate_student_password(length: int = 12) -> str:
    """Generate secure random password for students"""
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(random.choice(chars) for _ in range(length))


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

# ------------------------- Routes -------------------------

@app.get('/')
def root():
    return redirect(url_for('login'))

# ===== ADMIN ROUTES =====

@app.get('/admin/login')
def admin_login():
    return render_template('admin_login.html', app_title=APP_TITLE)

@app.post('/admin/login')
def admin_login_post():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    if not (username and password):
        return render_template('admin_login.html', app_title=APP_TITLE, error='Username and password required')
    
    conn = get_db()
    admin = conn.execute("SELECT id, password_hash FROM admin_users WHERE username=?", (username,)).fetchone()
    conn.close()
    
    if not admin or not verify_password(password, admin['password_hash']):
        return render_template('admin_login.html', app_title=APP_TITLE, error='Invalid credentials')
    
    session['admin_id'] = admin['id']
    session['admin_username'] = username
    return redirect(url_for('admin_dashboard'))

@app.get('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db()
    test = conn.execute("SELECT id, name, slug, status, start_time, end_time FROM tests WHERE slug=?", 
                       (CFG['test']['slug'],)).fetchone()
    
    # Get all submissions
    submissions = conn.execute("""
        SELECT s.id, s.respondent_id, r.name, r.email, r.student_id, s.score, s.total_points, s.violations_count, 
               s.violation_reason, s.finished_at, s.attempt_no
        FROM submissions s 
        JOIN respondents r ON s.respondent_id=r.id
        ORDER BY s.finished_at DESC
    """).fetchall()
    
    # Get student credentials count
    active_credentials = conn.execute("SELECT COUNT(*) as count FROM student_credentials WHERE status='active'").fetchone()['count']
    used_credentials = conn.execute("SELECT COUNT(*) as count FROM student_credentials WHERE status='used'").fetchone()['count']
    
    conn.close()
    
    return render_template('admin_dashboard.html', app_title=APP_TITLE, test=test, 
                         submissions=submissions, active_credentials=active_credentials,
                         used_credentials=used_credentials, CFG=CFG)

@app.get('/admin/credentials')
def admin_credentials():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db()
    credentials = conn.execute("""
        SELECT id, email, name, level, status, created_at, expires_at 
        FROM student_credentials 
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()
    
    return render_template('admin_credentials.html', app_title=APP_TITLE, credentials=credentials)


@app.post('/admin/delete-credential')
def delete_credential():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    email = request.form.get('email', '').strip()
    
    if not email:
        session['error_msg'] = 'Invalid email provided'
        return redirect(url_for('admin_credentials'))
    
    try:
        conn = get_db()
        conn.execute("DELETE FROM student_credentials WHERE email = ?", (email,))
        conn.commit()
        conn.close()
        session['success_msg'] = f'Credential for {email} removed successfully'
    except Exception as e:
        session['error_msg'] = f'Failed to remove credential: {str(e)}'
    
    return redirect(url_for('admin_credentials'))


@app.get('/admin/edit-credential')
def admin_edit_credential():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    email = (request.args.get('email') or '').strip().lower()
    if not email:
        session['error_msg'] = 'Invalid email'
        return redirect(url_for('admin_credentials'))
    conn = get_db()
    cred = conn.execute("SELECT id, email, name, level, status, expires_at FROM student_credentials WHERE email=?", (email,)).fetchone()
    conn.close()
    if not cred:
        session['error_msg'] = 'Credential not found'
        return redirect(url_for('admin_credentials'))
    return render_template('admin_edit_credential.html', app_title=APP_TITLE, cred=cred)


@app.post('/admin/update-credential')
def admin_update_credential():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    email = (request.form.get('email') or '').strip().lower()
    name = (request.form.get('name') or '').strip()
    level = (request.form.get('level') or 'NOVAS').upper()
    status = (request.form.get('status') or 'active')
    expires = (request.form.get('expires_at') or None)
    valid_levels = ['NOVAS','VOYAGERS','TITANS','LEGENDS']
    if level not in valid_levels:
        level = 'NOVAS'
    conn = get_db()
    try:
        conn.execute("UPDATE student_credentials SET name=?, level=?, status=?, expires_at=? WHERE email=?",
                     (name, level, status, expires, email))
        conn.close()
        session['success_msg'] = '✅ Credential updated'
    except Exception as e:
        session['error_msg'] = f'Failed to update: {str(e)[:100]}'
    return redirect(url_for('admin_credentials'))


@app.get('/admin/edit-question')
def admin_edit_question():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    qid = request.args.get('id')
    if not qid:
        session['error_msg'] = 'No question id'
        return redirect(url_for('admin_questions'))
    conn = get_db()
    row = conn.execute("SELECT id, question_id, text, image_url, option_a, option_b, option_c, option_d, correct_option FROM questions WHERE id=?", (qid,)).fetchone()
    conn.close()
    if not row:
        session['error_msg'] = 'Question not found'
        return redirect(url_for('admin_questions'))
    return render_template('admin_edit_question.html', app_title=APP_TITLE, q=row)


@app.post('/admin/update-question')
def admin_update_question():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    qid = request.form.get('id')
    if not qid:
        session['error_msg'] = 'No question id'
        return redirect(url_for('admin_questions'))
    text = (request.form.get('text') or '').strip()
    option_a = (request.form.get('option_a') or '').strip()
    option_b = (request.form.get('option_b') or '').strip()
    option_c = (request.form.get('option_c') or '').strip()
    option_d = (request.form.get('option_d') or '').strip()
    correct = (request.form.get('correct_option') or '').strip().lower()
    # Handle optional new image upload and/or delete flag
    f = request.files.get('image')
    img_rel = None
    if f and f.filename:
        # save to uploads then ensure saved to static
        temp_name = f"temp_img_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}_{f.filename}"
        temp_path = UPLOADS_DIR / temp_name
        f.save(str(temp_path))
        img_rel = ensure_image_saved(temp_name)

    delete_flag = (request.form.get('delete_image') or '') in ('1', 'on', 'true')

    conn = get_db()
    try:
        # Fetch current image URL so we can remove file if needed
        row = conn.execute("SELECT image_url FROM questions WHERE id=?", (qid,)).fetchone()
        old_image = row['image_url'] if row else ''

        # If a new image was uploaded, set it and remove old image file
        if img_rel:
            conn.execute("UPDATE questions SET text=?, option_a=?, option_b=?, option_c=?, option_d=?, correct_option=?, image_url=? WHERE id=?",
                         (text, option_a, option_b, option_c, option_d, correct, img_rel, qid))
            # attempt to remove old image file if it lives under assets/question_images
            try:
                if old_image and old_image.startswith('assets/question_images/'):
                    old_path = BASE_DIR / 'static' / old_image
                    if old_path.exists():
                        old_path.unlink()
            except Exception:
                pass
        else:
            # No new upload. If delete flag provided, clear image_url and remove file.
            if delete_flag and old_image:
                try:
                    if old_image.startswith('assets/question_images/'):
                        old_path = BASE_DIR / 'static' / old_image
                        if old_path.exists():
                            old_path.unlink()
                except Exception:
                    pass
                conn.execute("UPDATE questions SET text=?, option_a=?, option_b=?, option_c=?, option_d=?, correct_option=?, image_url='' WHERE id=?",
                             (text, option_a, option_b, option_c, option_d, correct, qid))
            else:
                # Normal update (no image change)
                conn.execute("UPDATE questions SET text=?, option_a=?, option_b=?, option_c=?, option_d=?, correct_option=? WHERE id=?",
                             (text, option_a, option_b, option_c, option_d, correct, qid))

        conn.commit()
        conn.close()
        session['success_msg'] = '✅ Question updated'
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        session['error_msg'] = f'Failed to update question: {str(e)[:120]}'
    return redirect(url_for('admin_questions'))


@app.get('/admin/seed-tutorial-images')
def admin_seed_tutorial_images():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    conn = get_db()
    test = conn.execute("SELECT id FROM tests WHERE slug=? AND level=?", (CFG['test']['slug'], 'NOVAS')).fetchone()
    if not test:
        conn.close()
        session['error_msg'] = 'Test (NOVAS) not found'
        return redirect(url_for('admin_questions'))
    test_id = test['id']
    set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type='tutorial'", (test_id,)).fetchone()
    if not set_row:
        conn.execute("INSERT INTO question_sets (test_id, set_type, imported_at, source_file) VALUES (?,?,?,?)", (test_id, 'tutorial', datetime.now(timezone.utc).isoformat(), 'seed'))
        set_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
    else:
        set_id = set_row['id']
    # Insert 5 tutorial image questions if not present
    existing = conn.execute("SELECT COUNT(*) AS c FROM questions WHERE set_id=?", (set_id,)).fetchone()['c']
    if existing >= 5:
        conn.close()
        session['warning_msg'] = 'Tutorial already has 5+ questions'
        return redirect(url_for('admin_questions'))
    samples = []
    for i in range(1,6):
        samples.append((set_id, f'T{i}', f'Tutorial image question {i}', f'assets/question_images/tutorial_img{i}.svg', 'Option A', 'Option B', 'Option C', 'Option D', 'a'))
    try:
        conn.executemany("""INSERT INTO questions (set_id, question_id, text, image_url, option_a, option_b, option_c, option_d, correct_option) VALUES (?,?,?,?,?,?,?,?,?)""", samples)
        conn.commit()
        conn.close()
        session['success_msg'] = '✅ Seeded 5 tutorial image questions'
    except Exception as e:
        conn.close()
        session['error_msg'] = f'Failed to seed: {str(e)[:120]}'
    return redirect(url_for('admin_questions'))


@app.get('/admin/questions')
def admin_questions():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    level_filter = (request.args.get('level') or '').upper()
    type_filter = (request.args.get('type') or '').lower()

    conn = get_db()

    # Fetch tutorial questions (shared) and main questions separately.
    tutorial_questions = []
    main_questions = []

    try:
        if type_filter == 'tutorial':
            # Only tutorial questions
            tutorial_questions = conn.execute("""
                SELECT q.id, q.question_id, q.text AS question_text, q.image_url, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_option,
                       qs.set_type AS type, t.level
                FROM questions q
                JOIN question_sets qs ON q.set_id = qs.id
                JOIN tests t ON qs.test_id = t.id
                WHERE qs.set_type = 'tutorial'
                ORDER BY q.id
            """).fetchall()
        elif type_filter == 'main' and level_filter:
            # Main questions filtered by level
            main_questions = conn.execute("""
                SELECT q.id, q.question_id, q.text AS question_text, q.image_url, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_option,
                       qs.set_type AS type, t.level
                FROM questions q
                JOIN question_sets qs ON q.set_id = qs.id
                JOIN tests t ON qs.test_id = t.id
                WHERE qs.set_type = 'main' AND t.level = ?
                ORDER BY q.id
            """, (level_filter,)).fetchall()
        else:
            # No filters: fetch both tutorial (shared) and main (all levels)
            tutorial_questions = conn.execute("""
                SELECT q.id, q.question_id, q.text AS question_text, q.image_url, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_option,
                       qs.set_type AS type, t.level
                FROM questions q
                JOIN question_sets qs ON q.set_id = qs.id
                JOIN tests t ON qs.test_id = t.id
                WHERE qs.set_type = 'tutorial'
                ORDER BY q.id
            """).fetchall()

            main_questions = conn.execute("""
                SELECT q.id, q.question_id, q.text AS question_text, q.image_url, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_option,
                       qs.set_type AS type, t.level
                FROM questions q
                JOIN question_sets qs ON q.set_id = qs.id
                JOIN tests t ON qs.test_id = t.id
                WHERE qs.set_type = 'main'
                ORDER BY t.level, q.id
            """).fetchall()
    finally:
        conn.close()

    # Combine lists into a single `questions` list for backwards-compatible templates
    questions = []
    if tutorial_questions:
        questions.extend(list(tutorial_questions))
    if main_questions:
        questions.extend(list(main_questions))

    # Pass both lists and combined list to template; template will render according to filters
    return render_template('admin_questions.html', 
                         app_title=APP_TITLE, 
                         tutorial_questions=tutorial_questions,
                         main_questions=main_questions,
                         questions=questions,
                         level_filter=level_filter,
                         type_filter=type_filter)


@app.get('/admin/import')
def admin_import_get():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    return render_template('admin_import.html', app_title=APP_TITLE)


@app.post('/admin/import')
def admin_import_post():
    if 'admin_id' not in session:
        abort(403)

    # Accept either uploaded CSV file or plain textarea
    # Format: email,level or email,level,password (if password omitted, defaults to 123456)
    emails_text = request.form.get('emails', '').strip()
    f = request.files.get('file')

    lines = []
    if emails_text:
        lines = [l.strip() for l in emails_text.splitlines() if l.strip()]
    elif f:
        contents = f.read().decode('utf-8')
        lines = [l.strip() for l in contents.splitlines() if l.strip()]
    else:
        return render_template('admin_import.html', app_title=APP_TITLE, error='No data provided')

    # Define valid levels
    valid_levels = ['NOVAS', 'VOYAGERS', 'TITANS', 'LEGENDS']

    conn = get_db()
    inserted = 0
    for line in lines:
        parts = [p.strip() for p in line.split(',')]
        
        # Parse email, level, and optional password
        email = parts[0].lower() if len(parts) > 0 else ''
        level = parts[1].upper() if len(parts) > 1 else 'NOVAS'
        password = parts[2] if len(parts) > 2 else '123456'
        
        # Validate email and level
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            continue
        if level not in valid_levels:
            level = 'NOVAS'
        
        pwd_hash = hash_password(password)
        try:
            conn.execute("INSERT INTO student_credentials (email, password_hash, level, status, created_at) VALUES (?, ?, ?, 'active', ?)",
                         (email, pwd_hash, level, datetime.now(timezone.utc).isoformat()))
            inserted += 1
        except sqlite3.IntegrityError:
            # already exists, update password and level
            conn.execute("UPDATE student_credentials SET password_hash=?, level=? WHERE email=?", (pwd_hash, level, email))

    conn.close()
    return redirect(url_for('admin_credentials'))

@app.post('/admin/generate-credentials')
def admin_generate_credentials():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    count = request.form.get('count', 10)
    try:
        count = min(int(count), 100)  # Max 100 at a time
    except:
        count = 10
    
    conn = get_db()
    generated = []
    
    for i in range(count):
        email = f"student_{datetime.now(timezone.utc).timestamp()}_{i}@test.local"
        password = generate_student_password()
        password_hash = hash_password(password)
        
        try:
            conn.execute("""
                INSERT INTO student_credentials (email, password_hash, status, created_at)
                VALUES (?, ?, 'active', ?)
            """, (email, password_hash, datetime.now(timezone.utc).isoformat()))
            
            generated.append({'email': email, 'password': password})
        except sqlite3.IntegrityError:
            continue
    
    conn.close()
    
    # Return as downloadable CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['email', 'password'])
    writer.writeheader()
    writer.writerows(generated)
    output.seek(0)
    
    filename = f"student_credentials_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')), 
                    as_attachment=True, download_name=filename, mimetype='text/csv')

@app.post('/admin/quiz-control')
def admin_quiz_control():
    if 'admin_id' not in session:
        abort(403)
    
    action = request.form.get('action')  # 'start' or 'end'
    
    conn = get_db()
    test = conn.execute("SELECT id FROM tests WHERE slug=?", (CFG['test']['slug'],)).fetchone()
    
    if action == 'start':
        conn.execute("UPDATE tests SET status=?, start_time=? WHERE id=?",
                    ('active', datetime.now(timezone.utc).isoformat(), test['id']))
    elif action == 'end':
        conn.execute("UPDATE tests SET status=?, end_time=? WHERE id=?",
                    ('ended', datetime.now(timezone.utc).isoformat(), test['id']))
    
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.get('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.post('/admin/delete-question')
def admin_delete_question():
    if 'admin_id' not in session:
        abort(403)

    qid = request.form.get('question_id')
    if not qid:
        session['error_msg'] = '❌ No question specified for deletion'
        return redirect(url_for('admin_questions'))

    conn = get_db()
    row = conn.execute("SELECT id, image_url, set_id FROM questions WHERE id=?", (qid,)).fetchone()
    if not row:
        conn.close()
        session['error_msg'] = '❌ Question not found'
        return redirect(url_for('admin_questions'))

    image_url = row['image_url']
    set_id = row['set_id']

    try:
        conn.execute("DELETE FROM questions WHERE id=?", (qid,))
        # If the question_set is now empty, remove it as well
        remaining = conn.execute("SELECT COUNT(*) as c FROM questions WHERE set_id=?", (set_id,)).fetchone()['c']
        if remaining == 0:
            conn.execute("DELETE FROM question_sets WHERE id=?", (set_id,))
        conn.commit()
    except Exception as e:
        conn.close()
        session['error_msg'] = f'❌ Failed to delete question: {str(e)[:80]}'
        return redirect(url_for('admin_questions'))

    conn.close()

    # Attempt to delete associated image file if it exists
    if image_url:
        try:
            img_path = BASE_DIR / image_url
            if img_path.exists():
                img_path.unlink()
        except Exception:
            pass

    session['success_msg'] = '✅ Question deleted successfully'
    return redirect(url_for('admin_questions'))

# ===== STUDENT ROUTES =====

@app.get('/login')
def login():
    test_status = check_quiz_status()
    return render_template('login.html',
        app_title=APP_TITLE,
        test_name=CFG['test']['name'],
        logo_path=CFG['branding']['logo_path'],
        test_status=test_status)

@app.post('/login')
def login_post():
    name_from_form = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '').strip()
    
    if not (email and password):
        return render_template('login.html', app_title=APP_TITLE, test_name=CFG['test']['name'],
                             error='Email and password required', test_status=check_quiz_status())
    
    # Check quiz status
    test_status = check_quiz_status()
    if test_status['status'] != 'active':
        return render_template('login.html', app_title=APP_TITLE, test_name=CFG['test']['name'],
                             error=f'Quiz is {test_status["status"]}', test_status=test_status)
    
    conn = get_db()
    
    # Check student credentials (only active accounts can log in)
    cred = conn.execute("SELECT id, level FROM student_credentials WHERE email=? AND status='active'", 
                       (email,)).fetchone()
    
    if not cred:
        conn.close()
        return render_template('login.html', app_title=APP_TITLE, test_name=CFG['test']['name'],
                             error='Invalid credentials', test_status=test_status)
    
    cred_id = cred['id']
    level = cred['level']
    cred_data = conn.execute("SELECT password_hash, name FROM student_credentials WHERE id=?", 
                            (cred_id,)).fetchone()
    
    if not verify_password(password, cred_data['password_hash']):
        conn.close()
        return render_template('login.html', app_title=APP_TITLE, test_name=CFG['test']['name'],
                             error='Invalid credentials', test_status=test_status)
    
    # If the student provided a name in the form, save it to credentials and respondents
    final_name = cred_data['name'] or ''
    if name_from_form:
        final_name = name_from_form
        try:
            conn.execute("UPDATE student_credentials SET name=? WHERE id=?", (final_name, cred_id))
        except Exception:
            pass

    # Get or create respondent (sync name)
    respondent = conn.execute("SELECT id FROM respondents WHERE email=?", (email,)).fetchone()
    if not respondent:
        conn.execute("INSERT INTO respondents (email, name, student_id, extra_json) VALUES (?,?,?,?)",
                    (email, final_name or 'Student', '', json.dumps({})))
        respondent_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
    else:
        respondent_id = respondent['id']
        # update respondent name if changed
        if final_name:
            try:
                conn.execute("UPDATE respondents SET name=? WHERE id=?", (final_name, respondent_id))
            except Exception:
                pass
    
    # Get test for the student's level
    test = conn.execute("SELECT id FROM tests WHERE slug=? AND level=?", (CFG['test']['slug'], level)).fetchone()
    if not test:
        conn.close()
        return render_template('login.html', app_title=APP_TITLE, test_name=CFG['test']['name'],
                             error=f'Quiz not available for your level', test_status=test_status)
    
    session_token = hashlib.md5(f"{email}{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()
    
    conn.execute("""
        INSERT INTO quiz_sessions (quiz_id, student_id, session_token, start_time, status)
        VALUES (?, ?, ?, ?, 'active')
    """, (test['id'], respondent_id, session_token, datetime.now(timezone.utc).isoformat()))
    
    conn.close()
    
    session['email'] = email
    session['respondent_id'] = respondent_id
    session['session_token'] = session_token
    session['test_id'] = test['id']
    session['name'] = final_name or 'Student'
    session['level'] = level
    
    # Go to instructions page
    return redirect(url_for('instructions'))

def check_quiz_status():
    """Check current quiz status"""
    conn = get_db()
    test = conn.execute("SELECT status, start_time, end_time FROM tests WHERE slug=?", 
                       (CFG['test']['slug'],)).fetchone()
    conn.close()
    
    if not test:
        return {'status': 'not_started', 'message': 'Quiz has not started yet'}
    
    if test['status'] == 'inactive':
        return {'status': 'not_started', 'message': 'Quiz has not started yet'}
    elif test['status'] == 'ended':
        return {'status': 'ended', 'message': 'Quiz has ended'}
    else:
        return {'status': 'active', 'message': 'Quiz is active'}

@app.get('/instructions')
def instructions():
    if 'respondent_id' not in session:
        return redirect(url_for('login'))
    
    level = session.get('level', 'NOVAS')
    
    return render_template('instructions.html',
        app_title=APP_TITLE,
        test_name=CFG['test']['name'],
        logo_path=CFG['branding']['logo_path'],
        instructions=CFG['test']['instructions_html'],
        level=level)

@app.post('/start-tutorial')
def start_tutorial():
    if 'respondent_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    test_id = session.get('test_id')
    
    # Get tutorial questions: prefer a tutorial set that actually contains questions.
    set_row = conn.execute(
        "SELECT qs.id FROM question_sets qs WHERE qs.test_id=? AND qs.set_type='tutorial' AND EXISTS (SELECT 1 FROM questions q WHERE q.set_id=qs.id) ORDER BY qs.id DESC LIMIT 1",
        (test_id,)
    ).fetchone()

    # If no populated tutorial set exists for the student's test, fall back to the NOVAS tutorial (shared)
    if not set_row:
        nov_test = conn.execute("SELECT id FROM tests WHERE slug=? AND level=?", (CFG['test']['slug'], 'NOVAS')).fetchone()
        if nov_test:
            set_row = conn.execute(
                "SELECT qs.id FROM question_sets qs WHERE qs.test_id=? AND qs.set_type='tutorial' AND EXISTS (SELECT 1 FROM questions q WHERE q.set_id=qs.id) ORDER BY qs.id DESC LIMIT 1",
                (nov_test['id'],)
            ).fetchone()
            if not set_row:
                # If NOVAS has no populated tutorial, try any tutorial set (even if empty) before importing
                set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type='tutorial' ORDER BY id DESC LIMIT 1", (nov_test['id'],)).fetchone()
                if not set_row:
                    # import default tutorial into NOVAS if missing
                    import_file_to_set(conn, nov_test['id'], 'tutorial', UPLOADS_DIR / 'tutorial_sample.csv')
                    set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type='tutorial' ORDER BY id DESC LIMIT 1", (nov_test['id'],)).fetchone()
        else:
            # As a last resort, try importing into the student's test
            import_file_to_set(conn, test_id, 'tutorial', UPLOADS_DIR / 'tutorial_sample.csv')
            set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type='tutorial' ORDER BY id DESC LIMIT 1", (test_id,)).fetchone()
    
    tutorial_questions = load_questions_for_set(conn, set_row['id'])
    conn.close()
    
    per_sec = mmss_to_seconds(CFG['test']['per_question_time_mmss'])
    
    return render_template('tutorial.html',
        app_title=APP_TITLE,
        test_name=CFG['test']['name'],
        per_question_seconds=per_sec,
        questions=tutorial_questions)

@app.post('/tutorial-completed')
def tutorial_completed():
    if 'respondent_id' not in session:
        return redirect(url_for('login'))
    
    level = session.get('level', 'NOVAS')
    return render_template('quiz_start.html',
        app_title=APP_TITLE,
        test_name=CFG['test']['name'],
        logo_path=CFG['branding']['logo_path'],
        level=level)

@app.post('/start-real-test')
def start_real_test():
    if 'respondent_id' not in session:
        return redirect(url_for('login'))
    
    respondent_id = session.get('respondent_id')
    test_id = session.get('test_id')
    
    conn = get_db()

    # Prevent users who have already completed the test from starting again
    email = session.get('email')
    if email:
        cred_status = conn.execute("SELECT status FROM student_credentials WHERE email=?", (email,)).fetchone()
        if cred_status and cred_status['status'] != 'active':
            conn.close()
            return render_template('blocked.html', app_title=APP_TITLE, reason='This account has already completed the test and cannot retake it.')
    
    # Verify quiz is still active
    quiz = conn.execute("SELECT status FROM tests WHERE id=?", (test_id,)).fetchone()
    if quiz['status'] != 'active':
        conn.close()
        return render_template('quiz_ended.html', app_title=APP_TITLE, 
                             message='Quiz has ended or not started yet')
    
    # Get main questions
    set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type='main'", 
                          (test_id,)).fetchone()
    if not set_row:
        import_file_to_set(conn, test_id, 'main', UPLOADS_DIR / 'main_sample.csv')
        set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type='main'", 
                              (test_id,)).fetchone()
    
    questions = load_questions_for_set(conn, set_row['id'])
    
    # Build randomization
    attempt_no = 1
    q_ids = [q['id'] for q in questions]
    q_order = q_ids[:]
    if CFG['test']['randomize_questions']:
        random.shuffle(q_order)
    
    options_order = {}
    if CFG['test']['randomize_options']:
        for q in questions:
            opts = ['a', 'b', 'c', 'd']
            random.shuffle(opts)
            options_order[q['id']] = opts
    else:
        for q in questions:
            options_order[q['id']] = ['a', 'b', 'c', 'd']
    
    conn.execute("""
        INSERT INTO randomization_maps (test_id, respondent_id, attempt_no, q_order_json, options_order_json)
        VALUES (?, ?, ?, ?, ?)
    """, (test_id, respondent_id, attempt_no, json.dumps(q_order), json.dumps(options_order)))
    
    conn.close()
    
    session['q_order'] = q_order
    session['options_order'] = options_order
    session['attempt_no'] = attempt_no
    session['started_at'] = datetime.now(timezone.utc).isoformat()
    
    per_sec = mmss_to_seconds(CFG['test']['per_question_time_mmss'])
    
    # Materialize questions
    ordered = []
    mapping = {q['id']: q for q in questions}
    for qid in q_order:
        q = mapping[qid]
        opts_keys = options_order[qid]
        opts_texts = [q['options'][k] for k in opts_keys]
        ordered.append({'id': qid, 'text': q['text'], 'image_url': q.get('image_url'), 'options': opts_texts})
    
    return render_template('quiz.html',
        app_title=APP_TITLE,
        test_name=CFG['test']['name'],
        logo_path=CFG['branding']['logo_path'],
        per_question_seconds=per_sec,
        max_tab_leaves=3,
        violation_action=CFG['test']['anti_cheat']['action'],
        questions=ordered)

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
        image_url = str(row.get('image_url', '') or '').strip()
        # Normalize and attempt to copy/download images into static assets
        image_url = ensure_image_saved(image_url)
        conn.execute("""
            INSERT INTO questions (set_id, question_id, text, image_url, option_a, option_b, option_c, option_d, correct_option)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (set_id, str(row['question_id']), str(row['question_text']), image_url,
              str(row.get('option_a','') or ''), str(row.get('option_b','') or ''),
              str(row.get('option_c','') or ''), str(row.get('option_d','') or ''),
              str(row['correct_option']).strip().lower()))
    return set_id



def load_questions_for_set(conn, set_id: int):
    rows = conn.execute("""
        SELECT question_id, text, image_url, option_a, option_b, option_c, option_d, correct_option 
        FROM questions WHERE set_id=? ORDER BY id ASC
    """, (set_id,)).fetchall()
    qlist = []
    for r in rows:
        q = {
            'id': r['question_id'],
            'text': r['text'],
            'image_url': r['image_url'] or '',
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

@app.get('/blocked')
def blocked():
    reason = request.args.get('reason', 'Policy violation detected')
    return render_template('blocked.html', app_title=APP_TITLE, reason=reason)

@app.post('/'+CFG['test']['slug']+'/submit')
def submit_quiz():
    respondent_id = session.get('respondent_id')
    test_id = session.get('test_id')
    q_order = session.get('q_order')
    options_order = session.get('options_order')
    
    if not all([respondent_id, test_id, q_order, options_order]):
        return redirect(url_for('login'))
    
    conn = get_db()
    
    # Verify quiz is active
    quiz = conn.execute("SELECT status FROM tests WHERE id=?", (test_id,)).fetchone()
    if quiz['status'] != 'active':
        conn.close()
        return render_template('quiz_ended.html', app_title=APP_TITLE, 
                             message='Quiz has been ended by administrator')
    
    # Get main questions
    set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type='main'", 
                          (test_id,)).fetchone()
    questions = load_questions_for_set(conn, set_row['id'])
    mapping = {q['id']: q for q in questions}
    
    score = 0.0
    total_points = float(len(q_order))
    details = []
    
    for qid in q_order:
        q = mapping[qid]
        opts_keys = options_order[qid]
        opts_texts = [q['options'][k] for k in opts_keys]
        given_text = request.form.get(qid, '').strip()
        
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
    
    violations = int(request.form.get('violations', '0') or 0)
    violation_reason = request.form.get('violation_reason', '')
    
    now = datetime.now(timezone.utc)
    conn.execute("""
        INSERT INTO submissions (test_id, respondent_id, attempt_no, score, total_points, started_at, 
                                finished_at, violations_count, violation_reason, details_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (test_id, respondent_id, 1, score, total_points, session.get('started_at', now.isoformat()),
          now.isoformat(), violations, violation_reason, json.dumps(details)))
    
    submission_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
    
    # Mark credential as used
    respondent = conn.execute("SELECT email FROM respondents WHERE id=?", (respondent_id,)).fetchone()
    conn.execute("UPDATE student_credentials SET status='used' WHERE email=?", (respondent['email'],))
    
    conn.close()
    
    percent = (score / total_points) * 100.0
    grade, desc = grade_from_percent(percent)
    
    # Generate certificate
    respondent_name_val = session.get('name', 'Student')
    if not respondent_name_val:
        respondent_name_val = 'Student'
    cert_path = BASE_DIR / f"certificate_{submission_id}_{respondent_id}.pdf"
    generate_certificate(cert_path, respondent_id, submission_id, score, total_points, percent, grade, desc, respondent_name_val)
    
    # Generate detailed results PDF
    results_path = BASE_DIR / f"results_{submission_id}_{respondent_id}.pdf"
    generate_results_pdf(results_path, submission_id, respondent_id, respondent_name_val, details, score, 
                        total_points, percent, grade, desc)
    
    session['last_submission_id'] = submission_id

    # Do NOT expose scores or downloadable certificates/results to students.
    # Certificates and detailed results are generated and stored on the server
    # but can only be downloaded by an admin via the admin dashboard.
    end_msg = CFG['test']['end_message_html']
    return render_template('thankyou.html',
        app_title=APP_TITLE,
        end_message=end_msg,
        cert_ready=False)

# Certificate generation

def respondent_name(conn, respondent_id):
    r = conn.execute("SELECT name FROM respondents WHERE id=?", (respondent_id,)).fetchone()
    if r and r['name']:
        return r['name']
    return 'Respondent'


def generate_certificate(path: Path, respondent_id: int, submission_id: int, score: float, total: float, percent: float, grade: str, desc: str, name: str = 'Student'):
    """Generate a professional A4 landscape certificate PDF.

    Design features:
    - A4 (landscape) suitable for printing
    - Blue, white, and gold color scheme
    - Top-centered logo, title 'CERTIFICATE', subtitle, recipient name
    - Centered body paragraph, date and signature areas at bottom
    - Gold seal badge and decorative geometric accents
    """
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph

    # Resolve recipient name
    recipient = name or 'Student'
    try:
        conn = get_db()
        r = conn.execute('SELECT name FROM respondents WHERE id=?', (respondent_id,)).fetchone()
        if r and r['name']:
            recipient = r['name']
    except Exception:
        pass

    # Page setup
    width, height = landscape(A4)
    c = canvas.Canvas(str(path), pagesize=(width, height))

    # Colors
    blue = colors.HexColor('#0B3D91')
    sky = colors.HexColor('#2B6CB0')
    gold = colors.HexColor('#D4AF37')
    light_grey = colors.HexColor('#F1F5F9')

    # Background
    c.setFillColor(colors.white)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Outer border - blue with gold inner trim
    outer_margin = 14*mm
    c.setStrokeColor(blue)
    c.setLineWidth(6)
    c.roundRect(outer_margin/2, outer_margin/2, width - outer_margin, height - outer_margin, 8*mm, stroke=1, fill=0)
    c.setStrokeColor(gold)
    c.setLineWidth(2)
    inset = outer_margin/2 + 6
    c.roundRect(inset, inset, width - outer_margin - 12, height - outer_margin - 12, 6*mm, stroke=1, fill=0)

    # Decorative header bars
    c.setFillColor(gold)
    c.rect(width*0.12, height - 28*mm, width*0.76, 6, fill=1, stroke=0)
    c.setFillColor(sky)
    c.rect(width*0.12, height - 32*mm, width*0.18, 6, fill=1, stroke=0)

    # Logo at top center
    logo_h = 26*mm
    logo_w = 70*mm
    try:
        logo_path_cfg = CFG.get('branding', {}).get('logo_path') if CFG else None
        logo_path = ASSETS_DIR / Path(logo_path_cfg).name if logo_path_cfg else ASSETS_DIR / 'logo.png'
        if logo_path.exists():
            logo = ImageReader(str(logo_path))
            c.drawImage(logo, (width - logo_w)/2, height - outer_margin - logo_h - 6*mm, width=logo_w, height=logo_h, preserveAspectRatio=True, mask='auto')
        else:
            c.setFont('Helvetica-Bold', 18)
            c.setFillColor(blue)
            c.drawCentredString(width/2, height - outer_margin - 12*mm, 'INSTITUTION NAME')
    except Exception:
        c.setFont('Helvetica-Bold', 18)
        c.setFillColor(blue)
        c.drawCentredString(width/2, height - outer_margin - 12*mm, 'INSTITUTION NAME')

    # Title and subtitle
    c.setFillColor(blue)
    c.setFont('Helvetica-Bold', 44)
    c.drawCentredString(width/2, height - outer_margin - logo_h - 22*mm, 'CERTIFICATE')
    c.setFont('Helvetica', 16)
    c.setFillColor(sky)
    c.drawCentredString(width/2, height - outer_margin - logo_h - 32*mm, 'For Outstanding Performance')

    # Divider
    c.setStrokeColor(light_grey)
    c.setLineWidth(1)
    c.line(width*0.18, height - outer_margin - logo_h - 36*mm, width*0.82, height - outer_margin - logo_h - 36*mm)

    # Recipient name
    c.setFillColor(colors.black)
    c.setFont('Helvetica-Bold', 36)
    c.drawCentredString(width/2, height/2 + 8*mm, recipient)

    # Body paragraph
    body = CFG.get('branding', {}).get('certificate', {}).get('paragraph1') or (
        'This certificate is proudly presented in recognition of exceptional achievement and steadfast dedication to academic excellence.'
    )
    style = ParagraphStyle('certBody', fontName='Helvetica', fontSize=12, leading=16, alignment=1, textColor=colors.HexColor('#333333'))
    p = Paragraph(body, style)
    text_w = width * 0.64
    p_w, p_h = p.wrap(text_w, 80*mm)
    p.drawOn(c, (width - p_w)/2, height/2 - 12*mm - p_h)

    # Signature and date lines
    sign_y = outer_margin + 24*mm
    c.setStrokeColor(colors.HexColor('#CCCCCC'))
    c.setLineWidth(0.8)
    # Date line (left)
    c.line(outer_margin + 10*mm, sign_y, outer_margin + 60*mm, sign_y)
    c.setFont('Helvetica', 10)
    c.setFillColor(colors.HexColor('#333333'))
    c.drawString(outer_margin + 8*mm, sign_y - 6*mm, 'Date')
    # Signature line (right)
    c.line(width - outer_margin - 60*mm, sign_y, width - outer_margin - 10*mm, sign_y)
    c.drawString(width - outer_margin - 58*mm, sign_y - 6*mm, 'Authorized Signature')

    # Optional signature images
    try:
        left_sig_cfg = CFG.get('branding', {}).get('certificate', {}).get('signature_left_path')
        right_sig_cfg = CFG.get('branding', {}).get('certificate', {}).get('signature_right_path')
        sig_h = 18*mm
        sig_w = 40*mm
        if left_sig_cfg:
            left_sig = ASSETS_DIR / Path(left_sig_cfg).name
            if left_sig.exists():
                c.drawImage(ImageReader(str(left_sig)), outer_margin + 8*mm, sign_y + 3*mm, width=sig_w, height=sig_h, mask='auto')
        if right_sig_cfg:
            right_sig = ASSETS_DIR / Path(right_sig_cfg).name
            if right_sig.exists():
                c.drawImage(ImageReader(str(right_sig)), width - outer_margin - 8*mm - sig_w, sign_y + 3*mm, width=sig_w, height=sig_h, mask='auto')
    except Exception:
        pass

    # Gold seal - layered circles
    seal_center_x = width*0.78
    seal_center_y = sign_y + 6*mm
    c.setFillColor(gold)
    c.circle(seal_center_x, seal_center_y, 26*mm, stroke=0, fill=1)
    c.setFillColor(colors.HexColor('#b8861b'))
    c.circle(seal_center_x, seal_center_y, 20*mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.circle(seal_center_x, seal_center_y, 10*mm, stroke=0, fill=1)
    c.setFillColor(gold)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(seal_center_x, seal_center_y - 2*mm, 'SEAL OF')
    c.drawCentredString(seal_center_x, seal_center_y - 8*mm, 'AUTHENTICITY')

    # Decorative corner accents (gold triangles)
    try:
        tri_size = 18*mm
        c.saveState()
        c.setFillColor(gold)
        # bottom-left
        c.translate(outer_margin/2 + 2, outer_margin/2 + 2)
        c.polygon([0,0, tri_size,0, 0,tri_size], stroke=0, fill=1)
        c.restoreState()

        c.saveState()
        c.setFillColor(gold)
        # top-right
        c.translate(width - outer_margin/2 - 2, height - outer_margin/2 - 2)
        c.rotate(180)
        c.polygon([0,0, tri_size,0, 0,tri_size], stroke=0, fill=1)
        c.restoreState()
    except Exception:
        pass

    # Footer small print
    c.setFillColor(colors.HexColor('#666666'))
    c.setFont('Helvetica', 8)
    footer_text = CFG.get('branding', {}).get('certificate', {}).get('footnote') or '© Institution Name • All rights reserved'
    c.drawCentredString(width/2, 6*mm, footer_text)

    c.showPage()
    c.save()



def generate_results_pdf(path: Path, submission_id: int, respondent_id: int, name: str, details: list, 
                        score: float, total: float, percent: float, grade: str, desc: str):
    """Generate detailed results PDF with all questions and answers"""
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#00d9ff'),
        spaceAfter=30,
        alignment=1  # center
    )
    story.append(Paragraph(f"Quiz Results Report", title_style))
    
    # Student info
    info_style = ParagraphStyle('Info', parent=styles['Normal'], fontSize=12)
    story.append(Paragraph(f"<b>Student Name:</b> {name}", info_style))
    story.append(Paragraph(f"<b>Submission ID:</b> {submission_id}", info_style))
    story.append(Paragraph(f"<b>Score:</b> {int(score)} / {int(total)} ({percent:.1f}%)", info_style))
    story.append(Paragraph(f"<b>Grade:</b> {grade} - {desc}", info_style))
    story.append(Spacer(1, 20))
    
    # Questions
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#bb86fc'))
    for i, detail in enumerate(details, 1):
        story.append(Paragraph(f"Question {i}: {detail['text'][:80]}...", heading_style))
        
        # Build answer table
        is_correct = detail['correct']
        correct_color = colors.HexColor('#00e676') if is_correct else colors.HexColor('#ff5252')
        
        data = [
            ['Field', 'Value'],
            ['Your Answer', detail['given_text'][:60]],
            ['Correct Answer', detail.get('correct_key', 'N/A')],
            ['Result', '✓ CORRECT' if is_correct else '✗ INCORRECT']
        ]
        
        table = Table(data, colWidths=[150, 350])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#252d38')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#00d9ff')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#1a1f28')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#333d4d')),
            ('BACKGROUND', (0, -1), (-1, -1), correct_color),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 15))
    
    # Build PDF
    doc.build(story)

@app.get('/download/certificate/<int:submission_id>/<int:respondent_id>')
def download_certificate(submission_id, respondent_id):
    # Only admins can download certificates
    if 'admin_id' not in session:
        abort(403)

    conn = get_db()
    respondent = conn.execute("SELECT name FROM respondents WHERE id=?", (respondent_id,)).fetchone()
    conn.close()

    if not respondent:
        abort(404)

    path = BASE_DIR / f"certificate_{submission_id}_{respondent_id}.pdf"
    if not path.exists():
        abort(404)

    name_safe = (respondent['name'] or 'Student').replace(' ', '_')
    filename = f"{name_safe}_Certificate_{submission_id}.pdf"
    return send_file(str(path), as_attachment=True, download_name=filename)

@app.get('/download/results/<int:submission_id>/<int:respondent_id>')
def download_results(submission_id, respondent_id):
    # Only admins can download detailed results
    if 'admin_id' not in session:
        abort(403)

    conn = get_db()
    respondent = conn.execute("SELECT name FROM respondents WHERE id=?", (respondent_id,)).fetchone()
    conn.close()

    if not respondent:
        abort(404)

    path = BASE_DIR / f"results_{submission_id}_{respondent_id}.pdf"
    if not path.exists():
        abort(404)

    name_safe = (respondent['name'] or 'Student').replace(' ', '_')
    filename = f"{name_safe}_Results_{submission_id}.pdf"
    return send_file(str(path), as_attachment=True, download_name=filename)

# ===== NEW ADMIN QUESTION UPLOAD ROUTES (with preview & approval) =====

@app.get('/admin/upload-questions')
def admin_upload_questions():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    return render_template('admin_upload_questions.html', app_title=APP_TITLE)


@app.post('/admin/upload-questions-preview')
def admin_upload_questions_preview():
    if 'admin_id' not in session:
        abort(403)
    
    set_type = (request.form.get('set_type') or 'main').strip().lower()
    level = (request.form.get('level') or 'NOVAS').upper() if set_type == 'main' else 'NOVAS'
    f = request.files.get('file')
    
    if not f:
        session['error_msg'] = '❌ No file selected'
        return redirect(url_for('admin_upload_questions'))
    
    valid_levels = ['NOVAS', 'VOYAGERS', 'TITANS', 'LEGENDS']
    if level not in valid_levels:
        level = 'NOVAS'
    
    # Save uploaded file temporarily
    temp_filename = f"temp_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}_{f.filename}"
    temp_path = UPLOADS_DIR / temp_filename
    f.save(str(temp_path))
    
    try:
        # Parse file
        if str(temp_path).lower().endswith('.xlsx'):
            df = pd.read_excel(temp_path, engine='openpyxl')
        else:
            df = pd.read_csv(temp_path)
        
        # Extract questions
        questions = []
        for _, row in df.iterrows():
            q = {
                'question_id': str(row.get('question_id', '') or '').strip(),
                'text': str(row.get('question_text', '') or '').strip(),
                'option_a': str(row.get('option_a', '') or '').strip(),
                'option_b': str(row.get('option_b', '') or '').strip(),
                'option_c': str(row.get('option_c', '') or '').strip(),
                'option_d': str(row.get('option_d', '') or '').strip(),
                'correct': str(row.get('correct_option', '') or '').strip().lower(),
                'image_url': str(row.get('image_url', '') or '').strip(),
            }
            if q['text'] and q['correct'] in ('a', 'b', 'c', 'd'):
                questions.append(q)
        
        if not questions:
            session['error_msg'] = '❌ No valid questions found in file. Ensure columns: question_id, question_text, option_a-d, correct_option'
            return redirect(url_for('admin_upload_questions'))
        
        # Pass to preview template
        return render_template('admin_upload_preview.html',
            app_title=APP_TITLE,
            set_type=set_type,
            level=level,
            filename=f.filename,
            questions=questions,
            questions_json=json.dumps(questions),
            temp_file=temp_filename)
    
    except Exception as e:
        session['error_msg'] = f'❌ Error parsing file: {str(e)[:100]}'
        return redirect(url_for('admin_upload_questions'))


@app.post('/admin/approve-questions')
def admin_approve_questions():
    if 'admin_id' not in session:
        abort(403)
    
    set_type = (request.form.get('set_type') or 'main').strip().lower()
    level = (request.form.get('level') or 'NOVAS').upper() if set_type == 'main' else 'NOVAS'
    temp_file = request.form.get('temp_file', '').strip()
    questions_json = request.form.get('questions_json', '[]')
    
    try:
        questions = json.loads(questions_json)
    except:
        session['error_msg'] = '❌ Invalid questions data'
        return redirect(url_for('admin_upload_questions'))
    
    if not questions or len(questions) == 0:
        session['error_msg'] = '❌ No questions to add'
        return redirect(url_for('admin_upload_questions'))
    
    conn = get_db()
    
    try:
        # Get test for selected level
        if set_type == 'tutorial':
            test = conn.execute("SELECT id FROM tests WHERE slug=? AND level=?", (CFG['test']['slug'], 'NOVAS')).fetchone()
        else:
            test = conn.execute("SELECT id FROM tests WHERE slug=? AND level=?", (CFG['test']['slug'], level)).fetchone()
        
        if not test:
            conn.close()
            session['error_msg'] = f'❌ Test not found for level {level}'
            return redirect(url_for('admin_upload_questions'))
        
        test_id = test['id']
        
        # Find or create question_set
        set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type=?", 
                              (test_id, set_type)).fetchone()
        if not set_row:
            conn.execute("INSERT INTO question_sets (test_id, set_type, imported_at, source_file) VALUES (?,?,?,?)",
                        (test_id, set_type, datetime.now(timezone.utc).isoformat(), f'upload_{level}_questions'))
            set_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
        else:
            set_id = set_row['id']
        
        # Insert all questions
        inserted_count = 0
        for q in questions:
            try:
                # Ensure image is saved under static assets and store relative path
                img_rel = ensure_image_saved(q.get('image_url', '') or '')
                conn.execute("""
                    INSERT INTO questions (set_id, question_id, text, image_url, option_a, option_b, option_c, option_d, correct_option)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (set_id, q.get('question_id',''), q.get('text',''), img_rel,
                      q.get('option_a',''), q.get('option_b',''), q.get('option_c',''), q.get('option_d',''), q.get('correct','')))
                inserted_count += 1
            except Exception as e:
                print(f'Error inserting question {q.get("question_id")}: {e}')
                continue
        
        conn.commit()
        conn.close()
        
        # Clean up temp file
        try:
            temp_path = UPLOADS_DIR / temp_file
            if temp_path.exists():
                temp_path.unlink()
        except:
            pass
        
        session['success_msg'] = f'✅ Successfully added {inserted_count} questions for level {level} ({set_type})'
        return redirect(url_for('admin_questions'))
    
    except Exception as e:
        conn.close()
        session['error_msg'] = f'❌ Error adding questions: {str(e)[:100]}'
        return redirect(url_for('admin_upload_questions'))

# ===== OLD ADMIN ROUTES (Updated) =====

@app.post('/admin/upload/<set_type>')
def admin_upload(set_type):
    if 'admin_id' not in session:
        abort(403)
    
    f = request.files.get('file')
    # For tutorial uploads we ignore any provided level and use NOVAS (shared tutorial set)
    if set_type == 'tutorial':
        level = 'NOVAS'
    else:
        level = request.form.get('level', 'NOVAS').upper()  # Get selected level
    
    if not f:
        return 'No file', 400
    
    # Validate level (for main uploads)
    valid_levels = ['NOVAS', 'VOYAGERS', 'TITANS', 'LEGENDS']
    if level not in valid_levels:
        level = 'NOVAS'
    
    path = UPLOADS_DIR / f"{set_type}_{level}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{f.filename}"
    f.save(str(path))
    
    conn = get_db()
    # Get test for the selected level
    test = conn.execute("SELECT id FROM tests WHERE slug=? AND level=?", 
                       (CFG['test']['slug'], level)).fetchone()
    
    if not test:
        conn.close()
        return f'Quiz not found for level {level}', 400
    
    import_file_to_set(conn, test['id'], set_type, path)
    conn.close()
    
    return redirect(url_for('admin_dashboard'))


@app.post('/admin/add-user')
def admin_add_user():
    if 'admin_id' not in session:
        abort(403)

    email = (request.form.get('email') or '').strip().lower()
    password = (request.form.get('password') or '').strip()
    level = (request.form.get('level') or 'NOVAS').upper()
    name = (request.form.get('name') or '').strip()

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email) or not password:
        return redirect(url_for('admin_credentials'))

    valid_levels = ['NOVAS', 'VOYAGERS', 'TITANS', 'LEGENDS']
    if level not in valid_levels:
        level = 'NOVAS'

    pwd_hash = hash_password(password)
    conn = get_db()
    try:
        conn.execute("INSERT INTO student_credentials (email, password_hash, name, level, status, created_at) VALUES (?, ?, ?, ?, 'active', ?)",
                     (email, pwd_hash, name, level, datetime.now(timezone.utc).isoformat()))
    except sqlite3.IntegrityError:
        # update existing
        conn.execute("UPDATE student_credentials SET password_hash=?, level=?, name=? WHERE email=?",
                     (pwd_hash, level, name, email))
    conn.close()
    return redirect(url_for('admin_credentials'))


@app.post('/admin/add-question')
def admin_add_question():
    if 'admin_id' not in session:
        abort(403)

    set_type = (request.form.get('set_type') or 'main').strip().lower()
    level = (request.form.get('level') or 'NOVAS').upper()
    qid = (request.form.get('question_id') or '').strip()
    text = (request.form.get('question_text') or '').strip()
    option_a = (request.form.get('option_a') or '').strip()
    option_b = (request.form.get('option_b') or '').strip()
    option_c = (request.form.get('option_c') or '').strip()
    option_d = (request.form.get('option_d') or '').strip()
    correct = (request.form.get('correct_option') or '').strip().lower()
    image_file = request.files.get('image')

    if not text or correct not in ('a','b','c','d'):
        session['error_msg'] = '❌ Question text and correct option required'
        return redirect(url_for('admin_dashboard'))

    valid_levels = ['NOVAS', 'VOYAGERS', 'TITANS', 'LEGENDS']
    if level not in valid_levels:
        level = 'NOVAS'

    # Save image if provided (accept all image types)
    image_url = ''
    try:
        if image_file and image_file.filename:
            img_dir = ASSETS_DIR / 'question_images'
            img_dir.mkdir(parents=True, exist_ok=True)
            fname = f"qimg_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}_{image_file.filename}"
            save_path = img_dir / fname
            image_file.save(str(save_path))
            image_url = str(save_path.relative_to(BASE_DIR))
    except Exception as e:
        session['warning_msg'] = f'⚠️ Image upload failed: {str(e)[:50]}'
        image_url = ''

    conn = get_db()
    
    # For tutorial: use first test (shared across all levels)
    # For main: use test for selected level
    if set_type == 'tutorial':
        test = conn.execute("SELECT id FROM tests WHERE slug=? AND level=?", (CFG['test']['slug'], 'NOVAS')).fetchone()
    else:
        test = conn.execute("SELECT id FROM tests WHERE slug=? AND level=?", (CFG['test']['slug'], level)).fetchone()
    
    if not test:
        conn.close()
        session['error_msg'] = '❌ Test not found for selected level'
        return redirect(url_for('admin_dashboard'))

    test_id = test['id']
    # find or create question_set for this test and set_type
    set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type=?", (test_id, set_type)).fetchone()
    if not set_row:
        conn.execute("INSERT INTO question_sets (test_id, set_type, imported_at, source_file) VALUES (?,?,?,?)", 
                     (test_id, set_type, datetime.now(timezone.utc).isoformat(), 'manual'))
        set_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
    else:
        set_id = set_row['id']

    # generate qid if missing
    if not qid:
        qid = f"Q{int(datetime.now(timezone.utc).timestamp())}"

    try:
        conn.execute("INSERT INTO questions (set_id, question_id, text, image_url, option_a, option_b, option_c, option_d, correct_option) VALUES (?,?,?,?,?,?,?,?,?)",
                     (set_id, qid, text, image_url, option_a, option_b, option_c, option_d, correct))
        conn.commit()
        session['success_msg'] = f'✅ Question added successfully' + (f' with image' if image_url else '')
    except Exception as e:
        session['error_msg'] = f'❌ Failed to add question: {str(e)[:50]}'
    
    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.get('/admin/submission-details/<int:submission_id>')
def admin_submission_details(submission_id):
    if 'admin_id' not in session:
        abort(403)
    
    conn = get_db()
    submission = conn.execute("""
        SELECT s.id, s.respondent_id, s.score, s.total_points, s.violations_count, s.violation_reason,
               s.started_at, s.finished_at, s.details_json, r.name, r.email
        FROM submissions s
        JOIN respondents r ON s.respondent_id = r.id
        WHERE s.id = ?
    """, (submission_id,)).fetchone()
    
    if not submission:
        conn.close()
        abort(404)
    
    try:
        details = json.loads(submission['details_json'])
    except:
        details = []
    
    conn.close()
    
    percent = (submission['score'] / submission['total_points'] * 100) if submission['total_points'] > 0 else 0
    grade, desc = grade_from_percent(percent)
    
    return render_template('submission_details.html',
        app_title=APP_TITLE,
        submission=submission,
        details=details,
        percent=f"{percent:.1f}",
        grade=grade,
        description=desc)

@app.get('/admin/export')
def export_csv():
    if 'admin_id' not in session:
        abort(403)
    
    conn = get_db()
    rows = conn.execute("""
        SELECT s.id, r.name, r.student_id, r.email, s.score, s.total_points, s.violations_count, 
               s.violation_reason, s.finished_at
        FROM submissions s 
        JOIN respondents r ON s.respondent_id=r.id 
        ORDER BY s.finished_at ASC
    """).fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["submission_id", "name", "student_id", "email", "score", "total_points", 
                    "violations", "violation_reason", "finished_at"])
    for r in rows:
        writer.writerow([r['id'], r['name'], r['student_id'], r['email'], r['score'], r['total_points'], 
                        r['violations_count'], r['violation_reason'] or '', r['finished_at']])
    
    output.seek(0)
    filename = f"{CFG['test']['slug']}_submissions_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.csv"
    return send_file(io.BytesIO(output.getvalue().encode('utf-8-sig')), 
                    as_attachment=True, download_name=filename, mimetype='text/csv')

@app.get('/admin/export.xlsx')
def export_excel():
    if 'admin_id' not in session:
        abort(403)
    
    conn = get_db()
    rows = conn.execute("""
        SELECT s.id, r.name, r.student_id, r.email, s.score, s.total_points, s.violations_count, 
               s.violation_reason, s.finished_at, s.details_json
        FROM submissions s 
        JOIN respondents r ON s.respondent_id=r.id 
        ORDER BY s.finished_at ASC
    """).fetchall()
    conn.close()
    
    summary = [{
        'submission_id': r['id'], 'name': r['name'], 'student_id': r['student_id'], 'email': r['email'],
        'score': r['score'], 'total_points': r['total_points'], 'violations': r['violations_count'],
        'violation_reason': r['violation_reason'] or '', 'finished_at': r['finished_at']
    } for r in rows]
    
    answers = []
    for r in rows:
        try:
            det = json.loads(r['details_json'])
        except:
            det = []
        for a in det:
            answers.append({
                'submission_id': r['id'], 'question_id': a.get('qid'), 'question': a.get('text'),
                'given_key': a.get('given_key'), 'given_text': a.get('given_text'), 
                'correct_key': a.get('correct_key'), 'correct': 'Yes' if a.get('correct') else 'No'
            })
    
    df_summary = pd.DataFrame(summary)
    df_answers = pd.DataFrame(answers)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as w:
        df_summary.to_excel(w, index=False, sheet_name='Submissions')
        if not df_answers.empty:
            df_answers.to_excel(w, index=False, sheet_name='Answers')
        meta = pd.DataFrame({'key': ['test_slug', 'generated_at'], 
                           'value': [CFG['test']['slug'], datetime.now(timezone.utc).isoformat()]})
        meta.to_excel(w, index=False, sheet_name='Meta')
    
    output.seek(0)
    filename = f"{CFG['test']['slug']}_submissions_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename, 
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.get('/admin/submissions')
def admin_submissions():
    """View all submissions with scores and student details"""
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db()
    
    # Get all submissions with respondent and student info
    submissions = conn.execute("""
        SELECT s.id, s.test_id, s.respondent_id, s.score, s.total_points, s.finished_at,
               s.violations_count, r.email, r.name, c.level
        FROM submissions s
        JOIN respondents r ON s.respondent_id = r.id
        LEFT JOIN student_credentials c ON r.email = c.email
        ORDER BY s.finished_at DESC
    """).fetchall()
    
    # Get test info
    tests = conn.execute("SELECT id, level FROM tests").fetchall()
    test_map = {t['id']: t['level'] for t in tests}
    
    conn.close()
    
    # Calculate percentages and badges
    results = []
    for sub in submissions:
        pct = (sub['score'] / sub['total_points'] * 100) if sub['total_points'] > 0 else 0
        results.append({
            'id': sub['id'],
            'email': sub['email'],
            'name': sub['name'],
            'level': sub['level'],
            'score': sub['score'],
            'total': sub['total_points'],
            'percentage': round(pct, 1),
            'finished_at': sub['finished_at'],
            'violations': sub['violations_count'],
            'test_level': test_map.get(sub['test_id'])
        })
    
    return render_template('admin_submissions.html',
        app_title=APP_TITLE,
        submissions=results)


@app.get('/admin/submission/<int:submission_id>')
def admin_submission_detail(submission_id):
    """View detailed submission results and generate certificate"""
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db()
    
    sub = conn.execute("""
        SELECT s.id, s.test_id, s.respondent_id, s.score, s.total_points, s.finished_at,
               s.violations_count, s.details_json, r.email, r.name, c.level
        FROM submissions s
        JOIN respondents r ON s.respondent_id = r.id
        LEFT JOIN student_credentials c ON r.email = c.email
        WHERE s.id = ?
    """, (submission_id,)).fetchone()
    
    if not sub:
        conn.close()
        abort(404)
    
    # Parse answers
    try:
        details = json.loads(sub['details_json'])
    except:
        details = []
    
    # Get test info
    test = conn.execute("SELECT name FROM tests WHERE id=?", (sub['test_id'],)).fetchone()
    
    conn.close()
    
    pct = (sub['score'] / sub['total_points'] * 100) if sub['total_points'] > 0 else 0
    
    return render_template('admin_submission_detail.html',
        app_title=APP_TITLE,
        sub=sub,
        test_name=test['name'] if test else 'Quiz',
        percentage=round(pct, 1),
        details=details)


@app.get('/admin/certificate/<int:submission_id>')
def admin_download_certificate(submission_id):
    """Download certificate PDF (admin only)"""
    if 'admin_id' not in session:
        abort(403)
    
    conn = get_db()
    
    sub = conn.execute("""
        SELECT s.id, s.test_id, s.respondent_id, s.score, s.total_points, s.finished_at,
               r.email, r.name, c.level
        FROM submissions s
        JOIN respondents r ON s.respondent_id = r.id
        LEFT JOIN student_credentials c ON r.email = c.email
        WHERE s.id = ?
    """, (submission_id,)).fetchone()
    
    if not sub:
        conn.close()
        abort(404)
    
    test = conn.execute("SELECT name FROM tests WHERE id=?", (sub['test_id'],)).fetchone()
    conn.close()
    
    # Generate certificate PDF
    pct = (sub['score'] / sub['total_points'] * 100) if sub['total_points'] > 0 else 0
    
    # Create PDF
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    # Background
    pdf.setFillColorRGB(0.95, 0.97, 1.0)
    pdf.rect(0, 0, width, height, fill=True)
    
    # Border
    pdf.setStrokeColorRGB(0.1, 0.3, 0.6)
    pdf.setLineWidth(3)
    pdf.rect(20*mm, 20*mm, width-40*mm, height-40*mm)
    
    # Title
    pdf.setFont("Helvetica-Bold", 48)
    pdf.setFillColorRGB(0.1, 0.3, 0.6)
    pdf.drawString(width/2 - 100*mm, height - 60*mm, "CERTIFICATE")
    
    # Subtitle
    pdf.setFont("Helvetica-Bold", 24)
    pdf.setFillColorRGB(0.2, 0.4, 0.7)
    pdf.drawString(width/2 - 80*mm, height - 90*mm, "OF ACHIEVEMENT")
    
    # Body text
    pdf.setFont("Helvetica", 14)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.drawString(50*mm, height - 130*mm, "This is to certify that")
    
    # Student name
    pdf.setFont("Helvetica-Bold", 20)
    pdf.setFillColorRGB(0.1, 0.3, 0.6)
    pdf.drawString(50*mm, height - 160*mm, sub['name'] or sub['email'])
    
    # Achievement text
    pdf.setFont("Helvetica", 14)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.drawString(50*mm, height - 190*mm, f"has successfully completed the {test['name'] if test else 'Quiz'} Quiz")
    pdf.drawString(50*mm, height - 210*mm, f"with a score of {sub['score']:.0f}/{sub['total_points']:.0f} ({pct:.1f}%)")
    
    # Level info
    pdf.setFont("Helvetica", 12)
    pdf.setFillColorRGB(0.2, 0.4, 0.7)
    pdf.drawString(50*mm, height - 240*mm, f"Level: {sub['level']} | Date: {sub['finished_at'][:10]}")
    
    pdf.save()
    buffer.seek(0)
    
    filename = f"Certificate_{sub['name']}_{submission_id}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')


# ===== BULK IMPORT ROUTES =====


@app.get('/admin/import-sample-questions')
def admin_import_sample_questions():
    """Bulk import sample 25 questions for each level"""
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    conn = get_db()
    levels_and_files = [
        ('NOVAS', UPLOADS_DIR / 'NOVAS_25_questions.csv'),
        ('VOYAGERS', UPLOADS_DIR / 'VOYAGERS_25_questions.csv'),
        ('TITANS', UPLOADS_DIR / 'TITANS_25_questions.csv'),
        ('LEGENDS', UPLOADS_DIR / 'LEGENDS_25_questions.csv'),
    ]
    
    total_imported = 0
    errors = []
    
    for level, file_path in levels_and_files:
        if not file_path.exists():
            errors.append(f"File not found: {file_path.name}")
            continue
        
        try:
            # Get test for this level
            test = conn.execute("SELECT id FROM tests WHERE slug=? AND level=?", 
                              (CFG['test']['slug'], level)).fetchone()
            if not test:
                errors.append(f"Test not found for level {level}")
                continue
            
            test_id = test['id']
            
            # Find or create main question set for this level
            set_row = conn.execute("SELECT id FROM question_sets WHERE test_id=? AND set_type='main'", 
                                  (test_id,)).fetchone()
            if not set_row:
                conn.execute("INSERT INTO question_sets (test_id, set_type, imported_at, source_file) VALUES (?,?,?,?)",
                            (test_id, 'main', datetime.now(timezone.utc).isoformat(), file_path.name))
                set_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()['id']
            else:
                set_id = set_row['id']
            
            # Parse and insert questions
            df = pd.read_csv(file_path)
            count = 0
            for _, row in df.iterrows():
                img_url = str(row.get('image_url', '') or '').strip()
                # Normalize image path
                img_url = ensure_image_saved(img_url) if img_url else ''
                
                try:
                    conn.execute("""
                        INSERT INTO questions (set_id, question_id, text, image_url, option_a, option_b, option_c, option_d, correct_option)
                        VALUES (?,?,?,?,?,?,?,?,?)
                    """, (set_id, str(row['question_id']), str(row['question_text']), img_url,
                          str(row['option_a']), str(row['option_b']), str(row['option_c']), str(row['option_d']),
                          str(row['correct_option']).lower().strip()))
                    count += 1
                except Exception as e:
                    print(f"Error inserting question {row.get('question_id')}: {e}")
            
            total_imported += count
            
        except Exception as e:
            errors.append(f"Error importing {level}: {str(e)[:100]}")
    
    conn.commit()
    conn.close()
    
    if total_imported > 0:
        session['success_msg'] = f'Successfully imported {total_imported} questions for all levels'
    if errors:
        session['warning_msg'] = ' | '.join(errors)
    
    return redirect(url_for('admin_dashboard'))


# Map old URL for submit endpoint
@app.post('/quiz/submit')
def legacy_submit():
    return submit_quiz()

# Initialize
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
