from __future__ import annotations
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pathlib import Path
import sqlite3, os, datetime as dt

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "nesforvia.db"
UPLOAD_DIR = BASE_DIR / "static" / "uploads" / "news"
APP_UPLOAD_DIR = BASE_DIR / "static" / "uploads" / "applications"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
APP_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("NESFORVIA_SECRET", "CHANGE-THIS-SECRET-KEY")

# CHANGE THESE BEFORE GOING PUBLIC.
ADMINS = {
    "max": {"name": "Emperor Max I", "password_hash": generate_password_hash(os.environ.get("MAX_ADMIN_PASSWORD", "Biscuit123!"))},
    "doom": {"name": "Emperor Doom", "password_hash": generate_password_hash(os.environ.get("DOOM_ADMIN_PASSWORD", "Doom123!"))},
}
PARTIES = ["Green Party", "Conservative Party", "Social Democratic Party"]
ALLOWED_IMAGE_EXTS = {"png", "jpg", "jpeg", "webp", "gif"}

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.executescript('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            image TEXT,
            author TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL,
            dob TEXT,
            discord TEXT,
            reason TEXT NOT NULL,
            file_path TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voter_name TEXT NOT NULL,
            voter_key TEXT NOT NULL UNIQUE,
            party TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        ''')
        defaults = {
            "notice": "Welcome to the official website of the Imperial Kingdoms of Nesforvia.",
            "elections_on": "0",
        }
        for k, v in defaults.items():
            con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))

def get_setting(key: str) -> str:
    with db() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else ""

def set_setting(key: str, value: str):
    with db() as con:
        con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

def is_admin():
    return session.get("admin") in ADMINS

def admin_required():
    if not is_admin():
        abort(403)

def save_file(file, folder: Path) -> str | None:
    if not file or file.filename == "":
        return None
    name = secure_filename(file.filename)
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    if ext not in ALLOWED_IMAGE_EXTS and folder == UPLOAD_DIR:
        return None
    safe = f"{dt.datetime.now().strftime('%Y%m%d%H%M%S')}_{name}"
    file.save(folder / safe)
    return f"uploads/{'news' if folder == UPLOAD_DIR else 'applications'}/{safe}"

@app.context_processor
def inject_globals():
    return {"notice": get_setting("notice"), "is_admin": is_admin(), "admin_name": ADMINS.get(session.get("admin"), {}).get("name")}

@app.route('/')
def home():
    with db() as con:
        news = con.execute("SELECT * FROM news ORDER BY id DESC LIMIT 4").fetchall()
    return render_template('home.html', news=news)

@app.route('/information')
def information():
    return render_template('information.html')

@app.route('/news')
def news_list():
    with db() as con:
        news = con.execute("SELECT * FROM news ORDER BY id DESC").fetchall()
    return render_template('news.html', news=news)

@app.route('/apply/<kind>', methods=['GET','POST'])
def apply(kind):
    if kind not in {"citizenship", "passport"}:
        abort(404)
    if request.method == 'POST':
        file_path = save_file(request.files.get('file'), APP_UPLOAD_DIR)
        with db() as con:
            con.execute("""INSERT INTO applications(type, full_name, email, dob, discord, reason, file_path, created_at)
                         VALUES(?,?,?,?,?,?,?,?)""",
                        (kind, request.form['full_name'], request.form['email'], request.form.get('dob'),
                         request.form.get('discord'), request.form['reason'], file_path, dt.datetime.now().strftime('%d %B %Y, %H:%M')))
        flash(f"Your {kind} application has been submitted.")
        return redirect(url_for('home'))
    return render_template('apply.html', kind=kind)

@app.route('/elections', methods=['GET','POST'])
def elections():
    elections_on = get_setting("elections_on") == "1"
    if request.method == 'POST' and elections_on:
        voter_name = request.form['voter_name'].strip()
        party = request.form['party']
        voter_key = voter_name.lower() + "|" + request.remote_addr
        if party not in PARTIES:
            abort(400)
        try:
            with db() as con:
                con.execute("INSERT INTO votes(voter_name, voter_key, party, created_at) VALUES(?,?,?,?)",
                            (voter_name, voter_key, party, dt.datetime.now().strftime('%d %B %Y, %H:%M')))
            flash("Your vote has been recorded.")
        except sqlite3.IntegrityError:
            flash("You have already voted. One person gets one vote.")
        return redirect(url_for('elections'))
    with db() as con:
        results = con.execute("SELECT party, COUNT(*) AS total FROM votes GROUP BY party").fetchall()
    return render_template('elections.html', elections_on=elections_on, parties=PARTIES, results=results)

@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username'].lower().strip()
        password = request.form['password']
        admin = ADMINS.get(username)
        if admin and check_password_hash(admin['password_hash'], password):
            session['admin'] = username
            return redirect(url_for('admin'))
        flash("Invalid admin login.")
    return render_template('login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/admin', methods=['GET','POST'])
def admin():
    admin_required()
    if request.method == 'POST':
        set_setting("notice", request.form.get("notice", ""))
        set_setting("elections_on", "1" if request.form.get("elections_on") else "0")
        flash("Settings saved.")
        return redirect(url_for('admin'))
    with db() as con:
        apps = con.execute("SELECT * FROM applications ORDER BY id DESC").fetchall()
        votes = con.execute("SELECT party, COUNT(*) AS total FROM votes GROUP BY party").fetchall()
    return render_template('admin.html', apps=apps, votes=votes, elections_on=get_setting("elections_on") == "1")

@app.route('/admin/news/new', methods=['POST'])
def admin_news_new():
    admin_required()
    img = save_file(request.files.get('image'), UPLOAD_DIR)
    with db() as con:
        con.execute("INSERT INTO news(title, body, image, author, created_at) VALUES(?,?,?,?,?)",
                    (request.form['title'], request.form['body'], img, admin_name := ADMINS[session['admin']]['name'], dt.datetime.now().strftime('%d %B %Y')))
    flash("News posted.")
    return redirect(url_for('admin'))

@app.route('/admin/application/<int:app_id>/<status>')
def update_application(app_id, status):
    admin_required()
    if status not in {"Approved", "Declined", "Pending"}:
        abort(400)
    with db() as con:
        con.execute("UPDATE applications SET status=? WHERE id=?", (status, app_id))
    return redirect(url_for('admin'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

