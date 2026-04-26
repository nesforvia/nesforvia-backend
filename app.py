import os
import sqlite3
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

DB = "/tmp/nesforvia.db"

ADMINS = {
    "max": os.environ.get("ADMIN_MAX_PASSWORD", "Biscuit123!"),
    "doom": os.environ.get("ADMIN_DOOM_PASSWORD", "Doom123!")
}


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        name TEXT,
        email TEXT,
        reason TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        body TEXT,
        image TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        voter_name TEXT,
        party TEXT,
        created_at TEXT,
        UNIQUE(voter_name)
    )
    """)

    c.execute("INSERT OR IGNORE INTO settings VALUES ('notice', 'Welcome to the Imperial Kingdoms of Nesforvia.')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('elections_on', 'off')")

    conn.commit()
    conn.close()


init_db()


def get_setting(key):
    conn = db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else ""


def set_setting(key, value):
    conn = db()
    conn.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_globals():
    return {
        "notice": get_setting("notice"),
        "elections_on": get_setting("elections_on")
    }


@app.route("/")
def home():
    conn = db()
    latest_news = conn.execute("SELECT * FROM news ORDER BY id DESC LIMIT 3").fetchall()
    conn.close()
    return render_template("index.html", latest_news=latest_news)


@app.route("/information")
def information():
    return render_template("information.html")


@app.route("/citizenship", methods=["GET", "POST"])
def citizenship():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        reason = request.form.get("reason")

        conn = db()
        conn.execute(
            "INSERT INTO applications (type, name, email, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Citizenship", name, email, reason, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        conn.close()

        flash("Citizenship application submitted.")
        return redirect(url_for("citizenship"))

    return render_template("citizenship.html")


@app.route("/passport", methods=["GET", "POST"])
def passport():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        reason = request.form.get("reason")

        conn = db()
        conn.execute(
            "INSERT INTO applications (type, name, email, reason, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Passport", name, email, reason, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        conn.close()

        flash("Passport application submitted.")
        return redirect(url_for("passport"))

    return render_template("passport.html")


@app.route("/news")
def news():
    conn = db()
    posts = conn.execute("SELECT * FROM news ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("news.html", posts=posts)


@app.route("/elections", methods=["GET", "POST"])
def elections():
    elections_on = get_setting("elections_on")

    if elections_on != "on":
        return render_template("elections.html", elections_on=False)

    if request.method == "POST":
        voter_name = request.form.get("voter_name")
        party = request.form.get("party")

        try:
            conn = db()
            conn.execute(
                "INSERT INTO votes (voter_name, party, created_at) VALUES (?, ?, ?)",
                (voter_name, party, datetime.now().strftime("%Y-%m-%d %H:%M"))
            )
            conn.commit()
            conn.close()
            flash("Vote submitted.")
        except sqlite3.IntegrityError:
            flash("You have already voted.")

        return redirect(url_for("elections"))

    return render_template("elections.html", elections_on=True)


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username").lower()
        password = request.form.get("password")

        if username in ADMINS and ADMINS[username] == password:
            session["admin"] = username
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin login.")

    return render_template("admin_login.html")


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = db()
    applications = conn.execute("SELECT * FROM applications ORDER BY id DESC").fetchall()
    posts = conn.execute("SELECT * FROM news ORDER BY id DESC").fetchall()
    votes = conn.execute("SELECT party, COUNT(*) as count FROM votes GROUP BY party").fetchall()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        applications=applications,
        posts=posts,
        votes=votes
    )


@app.route("/admin/notice", methods=["POST"])
@admin_required
def update_notice():
    notice = request.form.get("notice")
    set_setting("notice", notice)
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/elections", methods=["POST"])
@admin_required
def toggle_elections():
    status = request.form.get("status")
    set_setting("elections_on", "on" if status == "on" else "off")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/news", methods=["POST"])
@admin_required
def add_news():
    title = request.form.get("title")
    body = request.form.get("body")
    image = request.form.get("image")

    conn = db()
    conn.execute(
        "INSERT INTO news (title, body, image, created_at) VALUES (?, ?, ?, ?)",
        (title, body, image, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
