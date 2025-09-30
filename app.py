from flask import Flask,render_template,request,redirect,url_for
import sqlite3,os,datetime,smtplib,pytz
from apscheduler.schedulers.background import BackgroundScheduler
from email.message import EmailMessage
from flask import send_file



DB='tasks.db'
TZ=pytz.timezone('Asia/Kolkata')
MORNING_HOUR=8
EVENING_HOUR=20

"""
def init_db():
    c=conn().cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        created_at TEXT,
        submit_at TEXT,
        status TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        ts TEXT,
        text TEXT
    )''')
    conn().commit()
"""
def init_db():
    if not os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Create tables
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
    return sqlite3.connect(DB,check_same_thread=False)

def nowstr():
    return datetime.datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')

def get_tasks(filter_pending=False):
    with sqlite3.connect(DB) as c:
        cur=c.cursor()
        if filter_pending:
            cur.execute("SELECT * FROM tasks WHERE status!='completed' ORDER BY id")
        else:
            cur.execute("SELECT * FROM tasks ORDER BY id")
        return cur.fetchall()

def get_task(tid):
    with sqlite3.connect(DB) as c:
        cur=c.cursor()
        cur.execute("SELECT * FROM tasks WHERE id=?", (tid,))
        return cur.fetchone()

def get_logs(tid):
    with sqlite3.connect(DB) as c:
        cur=c.cursor()
        cur.execute("SELECT ts,text FROM logs WHERE task_id=? ORDER BY id", (tid,))
        return cur.fetchall()

def last_log(tid):
    with sqlite3.connect(DB) as c:
        cur=c.cursor()
        cur.execute("SELECT ts,text FROM logs WHERE task_id=? ORDER BY id DESC LIMIT 1", (tid,))
        return cur.fetchone()

def add_task(title,submit_at):
    with sqlite3.connect(DB) as c:
        c.execute("INSERT INTO tasks(title,created_at,submit_at,status) VALUES(?,?,?,?)",
                  (title, nowstr(), submit_at or '', 'not started'))

def add_log(tid,text):
    with sqlite3.connect(DB) as c:
        c.execute("INSERT INTO logs(task_id,ts,text) VALUES(?,?,?)",(tid,nowstr(),text))

def update_status(tid,status):
    with sqlite3.connect(DB) as c:
        c.execute("UPDATE tasks SET status=? WHERE id=?",(status,tid))


def send_email(subject,body,to_addrs):
    host=os.environ.get('EMAIL_HOST')
    port=int(os.environ.get('EMAIL_PORT','587'))
    user=os.environ.get('EMAIL_USER')
    pwd=os.environ.get('EMAIL_PASS')
    if not all([host,port,user,pwd,to_addrs]): return
    msg=EmailMessage()
    msg['Subject']=subject
    msg['From']=user
    msg['To']=to_addrs
    msg.set_content(body)
    s=smtplib.SMTP(host,port,timeout=30)
    try:
        s.starttls()
        s.login(user,pwd)
        s.send_message(msg)
    finally:
        s.quit()

def morning_job():
    tasks=get_tasks(filter_pending=True)
    if not tasks: return
    lines=[]
    for t in tasks:
        tid=t[0]; title=t[1]; submit=t[3]; status=t[4]
        lg=last_log(tid)
        last = f"{lg[0]} - {lg[1]}" if lg else "No logs yet"
        lines.append(f"Task #{tid}: {title}\nStatus: {status}\nSubmit by: {submit}\nLast log: {last}\n")
    body="Pending tasks summary:\n\n" + "\n".join(lines)
    to=os.environ.get('NOTIFY_TO')
    send_email("Morning: Pending tasks",body,to)

def evening_job():
    tasks=get_tasks()
    lines=[f"Please update these tasks today:\n"]
    for t in tasks:
        lines.append(f"#{t[0]} {t[1]} (Status: {t[4]})")
    body="\n".join(lines)
    to=os.environ.get('NOTIFY_TO')
    send_email("Evening: Task update request",body,to)

app=Flask(__name__)
init_db()
sched=BackgroundScheduler(timezone=TZ)
sched.add_job(morning_job,'cron',hour=MORNING_HOUR,minute=0)
sched.add_job(evening_job,'cron',hour=EVENING_HOUR,minute=0)
sched.start()

@app.route('/')
def index():
    tasks=get_tasks()
    return render_template('index.html',tasks=tasks)

@app.route('/create',methods=['GET','POST'])
def create():
    if request.method=='POST':
        title=request.form.get('title')
        submit_at=request.form.get('submit_at')
        if title:
            add_task(title,submit_at)
        return redirect(url_for('index'))
    return render_template('create.html')

@app.route('/task/<int:tid>',methods=['GET'])
def task_page(tid):
    t=get_task(tid)
    if not t: return "Not found",404
    logs=get_logs(tid)
    return render_template('task.html',task=t,logs=logs)

@app.route('/task/<int:tid>/add_log',methods=['POST'])
def add_log_route(tid):
    text=request.form.get('text')
    if text:
        add_log(tid,text)
        if request.form.get('status'):
            update_status(tid,request.form.get('status'))
    return redirect(url_for('task_page',tid=tid))

@app.route('/task/<int:tid>/set_status',methods=['POST'])
def set_status(tid):
    status=request.form.get('status')
    if status: update_status(tid,status)
    return redirect(url_for('task_page',tid=tid))

@app.route("/download_db")
def download_db():
    return send_file("tasks.db", as_attachment=True)
	
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

