from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect("bugtracker.db")

def init_db():
    db = get_db()
    cursor = db.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            password TEXT,
            role TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bugs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            severity TEXT,
            priority TEXT,
            status TEXT,
            assigned_to TEXT,
            created_by INTEGER,
            deadline TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bug_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bug_id INTEGER,
            comment TEXT,
            commenter TEXT,
            timestamp TEXT,
            status TEXT
        )
    ''')

    db.commit()
    db.close()

init_db()

# ---------------- ROUTES ----------------

@app.route('/')
def home():
    return render_template('login.html')


@app.route('/register', methods=['POST'])
def register():
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
        (
            request.form['name'],
            request.form['email'],
            request.form['password'],
            request.form['role']
        )
    )

    db.commit()
    db.close()
    return redirect('/')


@app.route('/login', methods=['POST'])
def login():
    db = get_db()
    cursor = db.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE email=? AND password=?",
        (request.form['email'], request.form['password'])
    )

    user = cursor.fetchone()
    db.close()

    if user:
        session['user_id'] = user[0]
        session['name'] = user[1]
        session['role'] = user[4]
        return redirect('/dashboard')

    return "Invalid Login"


# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')

    db = get_db()
    cursor = db.cursor()

    stats = {}

    if session['role'].lower() == 'admin':
        cursor.execute("SELECT COUNT(*) FROM bugs")
        stats['total'] = cursor.fetchone()[0]

        cursor.execute("SELECT status, COUNT(*) FROM bugs GROUP BY status")
        data = dict(cursor.fetchall())
        stats['open'] = data.get('Open', 0)
        stats['in_progress'] = data.get('In Progress', 0)
        stats['closed'] = data.get('Closed', 0)

        cursor.execute("SELECT assigned_to, COUNT(*) FROM bugs GROUP BY assigned_to")
        dev_stats = cursor.fetchall()

    else:
        cursor.execute(
            "SELECT COUNT(*) FROM bugs WHERE LOWER(assigned_to)=LOWER(?)",
            (session['name'],)
        )
        stats['total'] = cursor.fetchone()[0]

        cursor.execute(
            "SELECT status, COUNT(*) FROM bugs WHERE LOWER(assigned_to)=LOWER(?) GROUP BY status",
            (session['name'],)
        )
        data = dict(cursor.fetchall())
        stats['open'] = data.get('Open', 0)
        stats['in_progress'] = data.get('In Progress', 0)
        stats['closed'] = data.get('Closed', 0)

        dev_stats = []

    db.close()

    return render_template(
        'dashboard.html',
        name=session['name'],
        role=session['role'],
        stats=stats,
        dev_stats=dev_stats
    )


# ---------------- REPORT BUG ----------------
@app.route('/report_bug')
def report_bug():
    return render_template('report_bug.html')


@app.route('/add_bug', methods=['POST'])
def add_bug():
    db = get_db()
    cursor = db.cursor()

    deadline = request.form['deadline']

    cursor.execute(
        "INSERT INTO bugs (title, description, severity, priority, status, assigned_to, created_by, deadline) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            request.form['title'],
            request.form['description'],
            request.form['severity'],
            request.form['priority'],
            "Open",
            request.form['assigned_to'],
            session['user_id'],
            deadline
        )
    )

    bug_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO bug_comments (bug_id, comment, commenter, timestamp, status) VALUES (?,?,?,?,?)",
        (bug_id, "Bug created", session['name'], datetime.now(), "Open")
    )

    db.commit()
    db.close()

    return redirect('/view_bugs')


# ---------------- VIEW BUGS ----------------
@app.route('/view_bugs')
def view_bugs():
    if 'user_id' not in session:
        return redirect('/')

    db = get_db()
    cursor = db.cursor()

    if session['role'].lower() == 'admin':
        cursor.execute("SELECT * FROM bugs")
    else:
        cursor.execute(
            "SELECT * FROM bugs WHERE LOWER(assigned_to)=LOWER(?)",
            (session['name'],)
        )

    bugs = cursor.fetchall()
    db.close()

    return render_template(
        'view_bugs.html',
        bugs=bugs,
        now=datetime.now().strftime("%Y-%m-%d")
    )


# ---------------- UPDATE STATUS ----------------
@app.route('/update_status/<int:bug_id>', methods=['POST'])
def update_status(bug_id):
    db = get_db()
    cursor = db.cursor()

    new_status = request.form['status']

    cursor.execute("UPDATE bugs SET status=? WHERE id=?", (new_status, bug_id))

    cursor.execute(
        "INSERT INTO bug_comments (bug_id, comment, commenter, timestamp, status) VALUES (?,?,?,?,?)",
        (bug_id, f"Status changed to {new_status}", session['name'], datetime.now(), new_status)
    )

    db.commit()
    db.close()

    return redirect('/view_bugs')


# ---------------- BUG DETAILS ----------------
@app.route('/bug_details/<int:bug_id>', methods=['GET', 'POST'])
def bug_details(bug_id):
    db = get_db()
    cursor = db.cursor()

    if request.method == 'POST':
        comment = request.form['comment']
        cursor.execute(
            "INSERT INTO bug_comments (bug_id, comment, commenter, timestamp, status) VALUES (?,?,?,?,?)",
            (bug_id, comment, session['name'], datetime.now(), None)
        )
        db.commit()

    cursor.execute("SELECT * FROM bugs WHERE id=?", (bug_id,))
    bug = cursor.fetchone()

    cursor.execute("SELECT * FROM bug_comments WHERE bug_id=?", (bug_id,))
    comments = cursor.fetchall()

    db.close()

    return render_template('bug_details.html', bug=bug, comments=comments)


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


if __name__ == "__main__":
    app.run(debug=True)