from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
import threading
from flask_mail import Mail, Message
from models import db, User, Job, Application

# ================= APP =================
app = Flask(__name__)

# ---------- SESSION CONFIG (Render safe) ----------
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

# ---------- BASE DIR ----------
basedir = os.path.abspath(os.path.dirname(__file__))

# ---------- SECRET KEY ----------
app.secret_key = os.environ.get("SECRET_KEY", "dev-fallback-key")

# ================= DATABASE =================
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
with app.app_context():
    db.create_all()

# ================= EMAIL =================
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = app.config["MAIL_USERNAME"]

mail = Mail(app)

# ---------- ASYNC EMAIL ----------
def send_email_async(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
            print("✅ Email sent")
        except Exception as e:
            print("❌ Email failed:", e)

# ================= ROUTES =================

@app.route("/")
def home():
    return redirect(url_for("login"))

# ---------- SIGNUP ----------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        role = request.form["role"].lower()

        if User.query.filter_by(email=email).first():
            flash("User already exists", "error")
            return redirect("/login")

        user = User(username=username, email=email, password=password, role=role)
        db.session.add(user)
        db.session.commit()

        flash("Account created successfully", "success")
        return redirect("/login")

    return render_template("signup.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session.clear()
            session["user_id"] = user.id
            session["role"] = user.role.lower()
            session["username"] = user.username

            return redirect(
                "/recruiter/dashboard"
                if user.role.lower() == "recruiter"
                else "/seeker/dashboard"
            )

        flash("Invalid credentials", "error")
        return redirect("/login")

    return render_template("login.html")

# ---------- LOGOUT ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------- RECRUITER DASHBOARD ----------
@app.route("/recruiter/dashboard")
def recruiter_dashboard():
    if session.get("role") != "recruiter":
        return redirect("/login")

    recruiter_id = session["user_id"]

    jobs = Job.query.filter_by(posted_by=recruiter_id).all()
    applications = (
        Application.query
        .join(Job)
        .filter(Job.posted_by == recruiter_id)
        .all()
    )

    return render_template(
        "recruiter_dashboard.html",
        jobs=jobs,
        applications=applications,
        username=session["username"]
    )

# ---------- POST JOB ----------
@app.route("/post-job", methods=["GET", "POST"])
def post_job():
    if session.get("role") != "recruiter":
        return redirect("/login")

    if request.method == "POST":
        job = Job(
            title=request.form["title"],
            description=request.form["description"],
            location=request.form.get("location", ""),
            posted_by=session["user_id"]
        )
        db.session.add(job)
        db.session.commit()

        flash("Job posted", "success")
        return redirect("/recruiter/dashboard")

    return render_template("post_job.html")

# ---------- SEEKER DASHBOARD ----------
@app.route("/seeker/dashboard")
def seeker_dashboard():
    if session.get("role") != "seeker":
        return redirect("/login")

    jobs = Job.query.all()
    return render_template(
        "seeker_dashboard.html",
        jobs=jobs,
        username=session["username"]
    )

# ---------- APPLY JOB ----------
@app.route("/apply/<int:job_id>", methods=["POST"])
def apply_job(job_id):
    if session.get("role") != "seeker":
        return redirect("/login")

    user = db.session.get(User, session["user_id"])

    if Application.query.filter_by(job_id=job_id, user_id=user.id).first():
        flash("Already applied", "info")
        return redirect("/seeker/dashboard")

    app_obj = Application(
        job_id=job_id,
        user_id=user.id,
        cover_letter=request.form.get("cover_letter", ""),
        status="pending"
    )
    db.session.add(app_obj)
    db.session.commit()

    job = db.session.get(Job, job_id)
    msg = Message(
        "Application Submitted",
        recipients=[user.email]
    )
    msg.body = f"Hi {user.username}, your application for {job.title} was submitted."

    threading.Thread(target=send_email_async, args=(app, msg)).start()

    flash("Application submitted", "success")
    return redirect("/seeker/dashboard")

# ---------- ACCEPT ----------
@app.route("/accept/<int:app_id>", methods=["POST"])
def accept_applicant(app_id):
    if session.get("role") != "recruiter":
        return redirect("/login")

    application = db.session.get(Application, app_id)

    if application.status == "accepted":
        flash("Already accepted", "info")
        return redirect("/recruiter/dashboard")

    application.status = "accepted"
    db.session.commit()

    user = db.session.get(User, application.user_id)
    job = db.session.get(Job, application.job_id)

    msg = Message(
        f"Application Accepted for {job.title}",
        recipients=[user.email]
    )
    msg.body = f"Congratulations {user.username}, you are selected for {job.title}."

    threading.Thread(target=send_email_async, args=(app, msg)).start()

    flash("Applicant accepted", "success")
    return redirect("/recruiter/dashboard")

# ---------- REJECT ----------
@app.route("/reject/<int:app_id>", methods=["POST"])
def reject_applicant(app_id):
    if session.get("role") != "recruiter":
        return redirect("/login")

    application = db.session.get(Application, app_id)

    if application.status == "rejected":
        flash("Already rejected", "info")
        return redirect("/recruiter/dashboard")

    application.status = "rejected"
    db.session.commit()

    user = db.session.get(User, application.user_id)
    job = db.session.get(Job, application.job_id)

    msg = Message(
        f"Application Rejected for {job.title}",
        recipients=[user.email]
    )
    msg.body = f"Hi {user.username}, unfortunately your application was rejected."

    threading.Thread(target=send_email_async, args=(app, msg)).start()

    flash("Applicant rejected", "success")
    return redirect("/recruiter/dashboard")

# ---------- RUN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
