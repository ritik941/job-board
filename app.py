from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from flask_mail import Mail, Message
from models import db, User, Job, Application  # Import models

app = Flask(__name__)
# ================= EMAIL CONFIG =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')

app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = app.config['MAIL_USERNAME']

mail = Mail(app)
# =================================================

app.secret_key = os.environ.get('SECRET_KEY', 'dev-fallback-key')

# DATABASE SETUP
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'job_board.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# UPLOAD FOLDER
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# ----------------- ROUTES -----------------

@app.route('/')
def home():
    return redirect(url_for('login'))

# SIGNUP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form['role'].lower()  # store as lowercase

        if User.query.filter_by(email=email).first():
            flash('User already exists. Please login.', 'error')
            return redirect('/login')

        new_user = User(username=username, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! Login now.', 'success')
        return redirect('/login')

    return render_template('signup.html')

# LOGIN
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
            elif session['role'] == 'seeker':
                return redirect('/seeker/dashboard')
            else:
                flash('Invalid role assigned to this user.', 'error')
                return redirect('/login')
        else:
            flash('Invalid email or password.', 'error')
            return redirect('/login')

    return render_template('login.html')

# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# RECRUITER DASHBOARD
@app.route('/recruiter/dashboard')
def recruiter_dashboard():
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return redirect('/login')

    user_id = session['user_id']
    jobs = Job.query.filter_by(posted_by=user_id).all()
    return render_template('recruiter_dashboard.html', jobs=jobs, username=session['username'])

# POST JOB
@app.route('/post-job', methods=['GET', 'POST'])
def post_job():
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        location = request.form.get('location', '')
        user_id = session['user_id']

        new_job = Job(title=title, description=description, location=location, posted_by=user_id)
        db.session.add(new_job)
        db.session.commit()
        flash('Job posted successfully!', 'success')
        return redirect('/recruiter/dashboard')

    return render_template('post_job.html')

# JOB SEEKER DASHBOARD
@app.route('/seeker/dashboard')
def seeker_dashboard():
    if 'user_id' not in session or session.get('role') != 'seeker':
        return redirect('/login')

    user = User.query.get(session['user_id'])
    jobs = Job.query.all()  # all jobs, no filters
    return render_template('seeker_dashboard.html', jobs=jobs, username=session['username'])

# APPLY TO A JOB
@app.route('/apply/<int:job_id>', methods=['POST'])
def apply_job(job_id):
    if 'user_id' not in session or session.get('role') != 'seeker':
        return redirect('/login')

    user_id = session['user_id']
    user = User.query.get(user_id)

    # check if already applied
    existing = Application.query.filter_by(job_id=job_id, user_id=user_id).first()
    if existing:
        flash("You have already applied to this job.", "error")
        return redirect('/seeker/dashboard')

    cover_letter = request.form.get('cover_letter', '')

    application = Application(job_id=job_id, user_id=user_id, cover_letter=cover_letter)
    db.session.add(application)
    db.session.commit()

    # Send email confirmation
    try:
        job = Job.query.get(job_id)
        msg = Message(
            "Application Submitted",
            sender=app.config['MAIL_USERNAME'],
            recipients=[user.email]
        )
        msg.body = f"Hi {user.username},\n\nYour application for '{job.title}' has been submitted successfully.\n\nGood luck!"
        mail.send(msg)
    except Exception as e:
        print("Email sending failed:", e)

    flash("✅ Your application has been submitted!", "success")
    return redirect('/seeker/dashboard')

# ACCEPT APPLICANT
@app.route('/accept/<int:app_id>', methods=['POST'])
def accept_applicant(app_id):
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return redirect('/login')

    application = Application.query.get(app_id)
    if not application:
        flash("Application not found", "error")
        return redirect('/recruiter/dashboard')

    db.session.commit()

    try:
        user = User.query.get(application.user_id)
        job = Job.query.get(application.job_id)
        msg = Message(
            f"Application Accepted for {job.title}",
            sender=app.config['MAIL_USERNAME'],
            recipients=[user.email]
        )
        msg.body = f"Hi {user.username},\n\nCongratulations! Your application for '{job.title}' has been accepted by the recruiter.\n\nBest regards,\nJob Board Team"
        mail.send(msg)
    except Exception as e:
        print("Email sending failed:", e)

    flash("Applicant accepted and email sent!", "success")
    return redirect('/recruiter/dashboard')

# REJECT APPLICANT
@app.route('/reject/<int:app_id>', methods=['POST'])
def reject_applicant(app_id):
    if 'user_id' not in session or session.get('role') != 'recruiter':
        return redirect('/login')

    application = Application.query.get(app_id)
    if not application:
        flash("Application not found", "error")
        return redirect('/recruiter/dashboard')

    db.session.commit()

    try:
        user = User.query.get(application.user_id)
        job = Job.query.get(application.job_id)
        msg = Message(
            f"Application Rejected for {job.title}",
            sender=app.config['MAIL_USERNAME'],
            recipients=[user.email]
        )
        msg.body = f"Hi {user.username},\n\nWe are sorry to inform you that your application for '{job.title}' has been rejected by the recruiter.\n\nBest regards,\nJob Board Team"
        mail.send(msg)
    except Exception as e:
        print("Email sending failed:", e)

    flash("Applicant rejected and email sent!", "success")
    return redirect('/recruiter/dashboard')

# CREATE TABLES




if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
