from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3, os, datetime, pytz

DB = 'tasks.db'
TZ = pytz.timezone('Asia/Kolkata')
APP_NAME = "AURA"  # Augmented Unified Task Assistant

def init_db():
    if not os.path.exists(DB):
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created_at TEXT,
            submit_at TEXT,
            status TEXT
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            log TEXT,
            timestamp TEXT,
            FOREIGN KEY(task_id) REFERENCES tasks(id)
        )
        """)
        conn.commit()
        conn.close()

def conn():
    return sqlite3.connect(DB, check_same_thread=False)

def nowstr():
    return datetime.datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')

def get_tasks(filter_pending=False):
    with sqlite3.connect(DB) as c:
        cur = c.cursor()
        if filter_pending:
            cur.execute("SELECT * FROM tasks WHERE status!='completed' ORDER BY id")
        else:
            cur.execute("SELECT * FROM tasks ORDER BY id")
        return cur.fetchall()

def get_task(tid):
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        cur = c.cursor()
        cur.execute("SELECT * FROM tasks WHERE id=?", (tid,))
        return cur.fetchone()

def get_logs(tid):
    with sqlite3.connect(DB) as c:
        c.row_factory = sqlite3.Row
        cur = c.cursor()
        cur.execute("SELECT * FROM logs WHERE task_id=? ORDER BY id", (tid,))
        return cur.fetchall()

def add_task(title, submit_at):
    with sqlite3.connect(DB) as c:
        c.execute("INSERT INTO tasks(title, created_at, submit_at, status) VALUES(?,?,?,?)",
                  (title, nowstr(), submit_at or '', 'not started'))

def add_log(tid, text):
    with sqlite3.connect(DB) as c:
        c.execute("INSERT INTO logs(task_id, log, timestamp) VALUES(?,?,?)", (tid, text, nowstr()))

def update_status(tid, status):
    with sqlite3.connect(DB) as c:
        c.execute("UPDATE tasks SET status=? WHERE id=?", (status, tid))

def update_submit(tid, new_date):
    with sqlite3.connect(DB) as c:
        c.execute("UPDATE tasks SET submit_at=? WHERE id=?", (new_date, tid))

def delete_task(tid):
    with sqlite3.connect(DB) as c:
        c.execute("DELETE FROM logs WHERE task_id=?", (tid,))
        c.execute("DELETE FROM tasks WHERE id=?", (tid,))

def delete_log(log_id):
    with sqlite3.connect(DB) as c:
        c.execute("DELETE FROM logs WHERE id=?", (log_id,))

app = Flask(__name__)
init_db()

@app.route('/')
def index():
    tasks = get_tasks()
    return render_template('index.html', tasks=tasks, app_name=APP_NAME)

@app.route('/create', methods=['GET','POST'])
def create():
    if request.method == 'POST':
        title = request.form.get('title')
        submit_at = request.form.get('submit_at')
        if title:
            add_task(title, submit_at)
        return redirect(url_for('index'))
    return render_template('create.html', app_name=APP_NAME)

@app.route('/task/<int:tid>', methods=['GET','POST'])
def task_page(tid):
    task = get_task(tid)
    if not task:
        return "Not found", 404
    logs = get_logs(tid)
    return render_template('task.html', task=task, logs=logs, app_name=APP_NAME)

@app.route('/task/<int:tid>/add_log', methods=['POST'])
def add_log_route(tid):
    text = request.form.get('text')
    if text:
        add_log(tid, text)
    return redirect(url_for('task_page', tid=tid))

@app.route('/task/<int:tid>/set_status', methods=['POST'])
def set_status(tid):
    status = request.form.get('status')
    if status:
        update_status(tid, status)
    return redirect(url_for('task_page', tid=tid))

@app.route('/task/<int:tid>/update_submit', methods=['POST'])
def update_submit_route(tid):
    new_date = request.form.get('submit_at')
    if new_date:
        update_submit(tid, new_date)
    return redirect(url_for('task_page', tid=tid))

@app.route('/task/<int:tid>/delete', methods=['POST'])
def delete_task_route(tid):
    delete_task(tid)
    return redirect(url_for('index'))

@app.route('/log/<int:log_id>/delete', methods=['POST'])
def delete_log_route(log_id):
    delete_log(log_id)
    return redirect(request.referrer or url_for('index'))

@app.route("/download_db")
def download_db():
    return send_file("tasks.db", as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
