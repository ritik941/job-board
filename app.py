from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
from models import db, User, Job, Application

# ================= APP =================
app = Flask(__name__)

# ---------- SESSION CONFIG ----------
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

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
        Application.query.join(Job)
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

        flash("Job posted successfully", "success")
        return redirect("/recruiter/dashboard")

    return render_template("post_job.html")

# ---------- SEEKER DASHBOARD ----------
@app.route("/seeker/dashboard")
def seeker_dashboard():
    if session.get("role") != "seeker":
        return redirect("/login")

    user_id = session["user_id"]
    jobs = Job.query.all()
    applications = Application.query.filter_by(user_id=user_id).all()

    return render_template(
        "seeker_dashboard.html",
        jobs=jobs,
        applications=applications,
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

    application = Application(
        job_id=job_id,
        user_id=user.id,
        cover_letter=request.form.get("cover_letter", ""),
        status="pending"
    )
    db.session.add(application)
    db.session.commit()

    flash("Application submitted", "success")
    return redirect("/seeker/dashboard")

# ---------- ACCEPT ----------
@app.route("/accept/<int:app_id>", methods=["POST"])
def accept_applicant(app_id):
    if session.get("role") != "recruiter":
        return redirect("/login")

    application = db.session.get(Application, app_id)
    application.status = "accepted"
    db.session.commit()

    flash("Applicant accepted", "success")
    return redirect("/recruiter/dashboard")

# ---------- REJECT ----------
@app.route("/reject/<int:app_id>", methods=["POST"])
def reject_applicant(app_id):
    if session.get("role") != "recruiter":
        return redirect("/login")

    application = db.session.get(Application, app_id)
    application.status = "rejected"
    db.session.commit()

    flash("Applicant rejected", "success")
    return redirect("/recruiter/dashboard")

# ---------- RUN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
