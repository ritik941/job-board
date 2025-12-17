from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from flask_mail import Mail, Message
from models import db, User, Job, Application

app = Flask(__name__)

# ================= EMAIL CONFIG =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)
# ===============================================

# SECRET KEY
app.secret_key = os.environ.get('SECRET_KEY', 'dev-fallback-key')

# ================= DATABASE =====================
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'job_board.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
# ===============================================

# ================= UPLOAD FOLDER =================
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# ===============================================


# ----------------- ROUTES -----------------

@app.route('/')
def home():
    return redirect(url_for('login'))

# ---------- SIGNUP ----------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form['role'].lower()

        if User.query.filter_by(email=email).first():
            flash('User already exists. Please login.', 'error')
            return redirect('/login')

        new_user = User(username=username, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully! Login now.', 'success')
        return redirect('/login')

    return render_template('signup.html')


# ---------- LOGIN ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password_input = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password_input):
            session['user_id'] = user.id
            session['role'] = user.role.lower()
            session['username'] = user.username

            if session['role'] == 'recruiter':
                return redirect('/recruiter/dashboard')
            else:
                return redirect('/seeker/dashboard')

        flash('Invalid email or password.', 'error')
        return redirect('/login')

    return render_template('login.html')


# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ---------- RECRUITER DASHBOARD ----------
@app.route('/recruiter/dashboard')
def recruiter_dashboard():
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return redirect('/login')

    jobs = Job.query.filter_by(posted_by=session['user_id']).all()
    return render_template('recruiter_dashboard.html', jobs=jobs, username=session['username'])


# ---------- POST JOB ----------
@app.route('/post-job', methods=['GET', 'POST'])
def post_job():
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return redirect('/login')

    if request.method == 'POST':
        job = Job(
            title=request.form['title'],
            description=request.form['description'],
            location=request.form.get('location', ''),
            posted_by=session['user_id']
        )
        db.session.add(job)
        db.session.commit()

        flash('Job posted successfully!', 'success')
        return redirect('/recruiter/dashboard')

    return render_template('post_job.html')


# ---------- SEEKER DASHBOARD ----------
@app.route('/seeker/dashboard')
def seeker_dashboard():
    if 'user_id' not in session or session.get('role') != 'seeker':
        return redirect('/login')

    jobs = Job.query.all()
    return render_template('seeker_dashboard.html', jobs=jobs, username=session['username'])


# ---------- APPLY JOB ----------
@app.route('/apply/<int:job_id>', methods=['POST'])
def apply_job(job_id):
    if 'user_id' not in session or session.get('role') != 'seeker':
        return redirect('/login')

    user = User.query.get(session['user_id'])

    if Application.query.filter_by(job_id=job_id, user_id=user.id).first():
        flash("You have already applied.", "error")
        return redirect('/seeker/dashboard')

    application = Application(
        job_id=job_id,
        user_id=user.id,
        cover_letter=request.form.get('cover_letter', ''),
        status="pending"
    )
    db.session.add(application)
    db.session.commit()

    try:
        job = Job.query.get(job_id)
        msg = Message(
            "Application Submitted",
            recipients=[user.email]
        )
        msg.body = f"Hi {user.username},\n\nYour application for '{job.title}' has been submitted successfully."
        mail.send(msg)
    except Exception as e:
        print("❌ Email failed:", e)

    flash("Application submitted!", "success")
    return redirect('/seeker/dashboard')


# ---------- ACCEPT APPLICANT ----------
@app.route('/accept/<int:app_id>', methods=['POST'])
def accept_applicant(app_id):
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return redirect('/login')

    application = Application.query.get_or_404(app_id)
    application.status = "accepted"
    db.session.commit()

    user = User.query.get(application.user_id)
    job = Job.query.get(application.job_id)

    try:
        print("📧 Sending acceptance email to:", user.email)

        msg = Message(
            subject=f"Application Accepted for {job.title}",
            recipients=[user.email]
        )
        msg.body = f"""
Hi {user.username},

🎉 Congratulations!

Your application for "{job.title}" has been ACCEPTED.

Regards,
Job Board Team
"""
        mail.send(msg)
        print("✅ Acceptance email sent")

    except Exception as e:
        print("❌ Email sending failed:", e)

    flash("Applicant accepted & email sent!", "success")
    return redirect('/recruiter/dashboard')


# ---------- REJECT APPLICANT ----------
@app.route('/reject/<int:app_id>', methods=['POST'])
def reject_applicant(app_id):
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return redirect('/login')

    application = Application.query.get_or_404(app_id)
    application.status = "rejected"
    db.session.commit()

    user = User.query.get(application.user_id)
    job = Job.query.get(application.job_id)

    try:
        msg = Message(
            subject=f"Application Rejected for {job.title}",
            recipients=[user.email]
        )
        msg.body = f"Hi {user.username},\n\nYour application for '{job.title}' was rejected."
        mail.send(msg)
    except Exception as e:
        print("❌ Email failed:", e)

    flash("Applicant rejected & email sent!", "success")
    return redirect('/recruiter/dashboard')


# ---------- CREATE TABLES ----------
with app.app_context():
    db.create_all()


# ---------- RUN (RENDER READY) ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
