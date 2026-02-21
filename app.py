
from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3, os, datetime, pytz

DB = 'tasks.db'
TZ = pytz.timezone('Asia/Kolkata')
APP_NAME = "EON Alpha v4.0.0 @meetvora.in"
MORNING_HOUR = 8
EVENING_HOUR = 20

from apscheduler.schedulers.background import BackgroundScheduler
from email.message import EmailMessage
import smtplib

# ----------------- Database -----------------
def conn():
    con = sqlite3.connect(DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    if not os.path.exists(DB):
        with conn() as c:
            cur = c.cursor()
            cur.execute("""
            CREATE TABLE IF NOT EXISTS tasks(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                created_at TEXT,
                submit_at TEXT,
                status TEXT
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                log TEXT,
                timestamp TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS drops(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                content TEXT,
                created_at TEXT
            )
            """)
            c.commit()


def nowstr():
    return datetime.datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')

def get_tasks(filter_pending=False):
    with conn() as c:
        cur = c.cursor()
        if filter_pending:
            cur.execute("SELECT * FROM tasks WHERE status!='completed' ORDER BY id")
        else:
            cur.execute("SELECT * FROM tasks ORDER BY id")
        return cur.fetchall()

def get_task(tid):
    with conn() as c:
        cur = c.cursor()
        cur.execute("SELECT * FROM tasks WHERE id=?", (tid,))
        return cur.fetchone()

def get_logs(tid):
    with conn() as c:
        cur = c.cursor()
        cur.execute("SELECT * FROM logs WHERE task_id=? ORDER BY id", (tid,))
        return cur.fetchall()

def last_log(tid):
    with conn() as c:
        cur = c.cursor()
        cur.execute("SELECT * FROM logs WHERE task_id=? ORDER BY id DESC LIMIT 1", (tid,))
        return cur.fetchone()

def add_task(title, submit_at):
    with conn() as c:
        c.execute("INSERT INTO tasks(title,created_at,submit_at,status) VALUES(?,?,?,?)",
                  (title, nowstr(), submit_at or '', 'not started'))

def add_log(tid, text):
    with conn() as c:
        c.execute("INSERT INTO logs(task_id,log,timestamp) VALUES(?,?,?)",(tid,text,nowstr()))

def update_status(tid, status):
    with conn() as c:
        c.execute("UPDATE tasks SET status=? WHERE id=?",(status,tid))

def update_submit(tid, submit_at):
    with conn() as c:
        c.execute("UPDATE tasks SET submit_at=? WHERE id=?",(submit_at,tid))

def delete_task(tid):
    with conn() as c:
        c.execute("DELETE FROM tasks WHERE id=?", (tid,))
        c.execute("DELETE FROM logs WHERE task_id=?", (tid,))

def delete_log(log_id):
    with conn() as c:
        c.execute("DELETE FROM logs WHERE id=?", (log_id,))

# --------------- Drops Functions ----------------
def add_drop(title, content):
    with conn() as c:
        c.execute("INSERT INTO drops(title, content, created_at) VALUES(?,?,?)",
                  (title, content, nowstr()))

def get_drops():
    with conn() as c:
        cur = c.cursor()
        cur.execute("SELECT * FROM drops ORDER BY id DESC")
        return cur.fetchall()

def get_drop(did):
    with conn() as c:
        cur = c.cursor()
        cur.execute("SELECT * FROM drops WHERE id=?", (did,))
        return cur.fetchone()

def delete_drop(did):
    with conn() as c:
        c.execute("DELETE FROM drops WHERE id=?", (did,))

"""
# ----------------- Email (optional) -----------------
def send_email(subject, body, to_addrs):
    host = os.environ.get('EMAIL_HOST')
    port = int(os.environ.get('EMAIL_PORT','587'))
    user = os.environ.get('EMAIL_USER')
    pwd = os.environ.get('EMAIL_PASS')
    if not all([host,port,user,pwd,to_addrs]): return
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = user
    msg['To'] = to_addrs
    msg.set_content(body)
    s = smtplib.SMTP(host, port, timeout=30)
    try:
        s.starttls()
        s.login(user, pwd)
        s.send_message(msg)
    finally:
        s.quit()

def morning_job():
    tasks = get_tasks(filter_pending=True)
    if not tasks: return
    lines = []
    for t in tasks:
        tid = t['id']; title = t['title']; submit = t['submit_at']; status = t['status']
        lg = last_log(tid)
        last = f"{lg['timestamp']} - {lg['log']}" if lg else "No logs yet"
        lines.append(f"Task #{tid}: {title}\nStatus: {status}\nSubmit by: {submit}\nLast log: {last}\n")
    body = "Pending tasks summary:\n\n" + "\n".join(lines)
    to = os.environ.get('NOTIFY_TO')
    send_email("Morning: Pending tasks", body, to)

def evening_job():
    tasks = get_tasks()
    lines = [f"Please update these tasks today:\n"]
    for t in tasks:
        lines.append(f"#{t['id']} {t['title']} (Status: {t['status']})")
    body = "\n".join(lines)
    to = os.environ.get('NOTIFY_TO')
    send_email("Evening: Task update request", body, to)
"""

# ----------------- Flask -----------------
app = Flask(__name__)
init_db()

"""
sched = BackgroundScheduler(timezone=TZ)
sched.add_job(morning_job,'cron',hour=MORNING_HOUR,minute=0)
sched.add_job(evening_job,'cron',hour=EVENING_HOUR,minute=0)
sched.start()
"""

# ----------------- Routes -----------------
@app.route('/')
def index():
    tasks = get_tasks()
    return render_template('index.html', tasks=tasks, app_name=APP_NAME)

@app.route('/create', methods=['GET','POST'])
def create():
    if request.method=='POST':
        title = request.form.get('title')
        submit_at = request.form.get('submit_at')
        if title:
            add_task(title, submit_at)
        return redirect(url_for('index'))
    return render_template('create.html', app_name=APP_NAME)

@app.route('/task/<int:tid>', methods=['GET'])
def task_page(tid):
    t = get_task(tid)
    if not t: return "Not found",404
    logs = get_logs(tid)
    return render_template('task.html', task=t, logs=logs, app_name=APP_NAME)

@app.route('/task/<int:tid>/add_log', methods=['POST'])
def add_log_route(tid):
    text = request.form.get('text')
    if text:
        add_log(tid,text)
        if request.form.get('status'):
            update_status(tid,request.form.get('status'))
    return redirect(url_for('task_page',tid=tid))

@app.route('/task/<int:tid>/set_status', methods=['POST'])
def set_status(tid):
    status = request.form.get('status')
    if status: update_status(tid,status)
    return redirect(url_for('task_page',tid=tid))

@app.route('/task/<int:tid>/update_submit', methods=['POST'])
def update_submit_route(tid):
    submit_at = request.form.get('submit_at')
    if submit_at:
        update_submit(tid, submit_at)
    return redirect(url_for('task_page',tid=tid))

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
    return send_file(DB, as_attachment=True)

@app.route('/drops')
def drops_index():
    drops = get_drops()
    return render_template('drops_index.html', drops=drops, app_name=APP_NAME)

@app.route('/drops/create', methods=['GET','POST'])
def create_drop():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        if title and content:
            add_drop(title, content)
        return redirect(url_for('drops_index'))
    return render_template('create_drop.html', app_name=APP_NAME)

@app.route('/drops/<int:did>')
def drop_page(did):
    d = get_drop(did)
    if not d: return "Not found", 404
    return render_template('drop.html', drop=d, app_name=APP_NAME)

@app.route('/drops/<int:did>/delete', methods=['POST'])
def delete_drop_route(did):
    delete_drop(did)
    return redirect(url_for('drops_index'))


# ----------------- Run -----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
