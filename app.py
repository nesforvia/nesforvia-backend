import os
import psycopg2
import psycopg2.extras
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

DATABASE_URL = os.environ.get("DATABASE_URL")

ADMINS = {
    "max": os.environ.get("ADMIN_MAX_PASSWORD", "Biscuit123!"),
    "doom": os.environ.get("ADMIN_DOOM_PASSWORD", "Doom123!")
}


def db():
    return psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor
    )


def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id SERIAL PRIMARY KEY,
        type TEXT,
        name TEXT,
        email TEXT,
        discord TEXT,
        dob TEXT,
        region TEXT,
        reason TEXT,
        contribution TEXT,
        agreement TEXT,
        citizenship_status TEXT,
        passport_reason TEXT,
        status TEXT DEFAULT 'Pending',
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS news (
        id SERIAL PRIMARY KEY,
        title TEXT,
        body TEXT,
        image TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        id SERIAL PRIMARY KEY,
        voter_name TEXT UNIQUE,
        party TEXT,
        created_at TEXT
    )
    """)

    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
        ("notice", "Welcome to the Imperial Kingdoms of Nesforvia.")
    )

    cur.execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING",
        ("elections_on", "off")
    )

    conn.commit()
    cur.close()
    conn.close()


init_db()


def get_setting(key):
    conn = db()
    row = conn.execute("SELECT value FROM settings WHERE key=%s", (key,)).fetchone()
    conn.close()
    return row["value"] if row else ""


def set_setting(key, value):
    conn = db()
    conn.execute("REPLACE INTO settings (key, value) VALUES (%s, %s)", (key, value))
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
        conn = db()
        conn.execute("""
            INSERT INTO applications (
                type, name, email, discord, dob, region, reason,
                contribution, agreement, citizenship_status, passport_reason,
                status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            "Citizenship",
            request.form.get("name"),
            request.form.get("email"),
            request.form.get("discord"),
            request.form.get("dob"),
            request.form.get("region"),
            request.form.get("reason"),
            request.form.get("contribution"),
            request.form.get("agreement"),
            None,
            None,
            "Pending",
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))
        conn.commit()
        conn.close()

        flash("Citizenship application submitted.")
        return redirect(url_for("citizenship"))

    return render_template("apply.html", kind="citizenship")


@app.route("/passport", methods=["GET", "POST"])
def passport():
    if request.method == "POST":
        conn = db()
        conn.execute("""
            INSERT INTO applications (
                type, name, email, discord, dob, region, reason,
                contribution, agreement, citizenship_status, passport_reason,
                status, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            "Passport",
            request.form.get("name"),
            request.form.get("email"),
            request.form.get("discord"),
            request.form.get("dob"),
            request.form.get("region"),
            request.form.get("reason"),
            None,
            None,
            request.form.get("citizenship_status"),
            request.form.get("passport_reason"),
            "Pending",
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))
        conn.commit()
        conn.close()

        flash("Passport application submitted.")
        return redirect(url_for("passport"))

    return render_template("apply.html", kind="passport")

@app.route("/admin/application/<int:app_id>/<status>")
@admin_required
def update_application_status(app_id, status):
    if status not in ["Approved", "Declined", "Pending"]:
        flash("Invalid status.")
        return redirect(url_for("admin_dashboard"))

    conn = db()
    conn.execute(
        "UPDATE applications SET status=%s WHERE id=%s",
        (status, app_id)
    )
    conn.commit()
    conn.close()

    flash(f"Application marked as {status}.")
    return redirect(url_for("admin_dashboard"))

@app.route("/news")
def news():
    conn = db()
    posts = conn.execute("SELECT * FROM news ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("news.html", posts=posts)


@app.route("/elections", methods=["GET", "POST"])
def elections():
    elections_on = get_setting("elections_on")

    if request.method == "POST" and elections_on == "on":
        voter_name = request.form.get("voter_name")
        party = request.form.get("party")

        try:
            conn = db()
            cur = conn.cursor()

            cur.execute(
                "INSERT INTO votes (voter_name, party, created_at) VALUES (%s, %s, %s)",
                (voter_name, party, datetime.now().strftime("%Y-%m-%d %H:%M"))
            )

            conn.commit()
            cur.close()
            conn.close()

            flash("Vote submitted.")

        except Exception:
            flash("You have already voted.")

        return redirect(url_for("elections"))

    conn = db()
    cur = conn.cursor()

    cur.execute("SELECT party, COUNT(*) as count FROM votes GROUP BY party")
    votes = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "elections.html",
        elections_on=elections_on,
        votes=votes
    )

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username").lower()
        password = request.form.get("password")

        if username in ADMINS and ADMINS[username] == password:
            session["admin"] = username
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin login.")

    return render_template("login.html")


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    conn = db()
    applications = conn.execute("SELECT * FROM applications ORDER BY id DESC").fetchall()
    posts = conn.execute("SELECT * FROM news ORDER BY id DESC").fetchall()
    votes = conn.execute("SELECT party, COUNT(*) as count FROM votes GROUP BY party").fetchall()
    conn.close()

    return render_template(
    "admin.html",
    applications=applications,
    posts=posts,
    votes=votes,
    admin_name=session.get("admin")
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
        "INSERT INTO news (title, body, image, created_at) VALUES (%s, %s, %s, %s)",
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
