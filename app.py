from flask import (
    Flask, render_template, request, redirect,
    session, url_for, flash, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Job, Application
import os

# ================= APP =================
app = Flask(__name__)
app.config["PREFERRED_URL_SCHEME"] = "https"


# ================= SECRET KEY =================
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# ================= SESSION CONFIG =================

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE = os.environ.get("RENDER") == "true"
)



# ================= DATABASE CONFIG =================
DATABASE_URL = os.environ.get("DATABASE_URL")

# LOCAL FALLBACK (VERY IMPORTANT)
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///job_board.db"

# Fix postgres:// issue
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text("""
            ALTER TABLE application
            ADD COLUMN IF NOT EXISTS resume VARCHAR(255);
        """))
        db.session.commit()
        print("Resume column ready")
    except Exception as e:
        db.session.rollback()
        print("DB error:", e)


with app.app_context():
    db.create_all()

# ================= RESUME UPLOAD =================
UPLOAD_FOLDER = "upload"
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/upload/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ================= HOME =================
@app.route("/")
def home():
    return redirect("/login")

# ================= SIGNUP =================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        if User.query.filter_by(email=request.form["email"]).first():
            flash("User already exists", "error")
            return redirect("/signup")

        user = User(
            username=request.form["username"],
            email=request.form["email"],
            password=generate_password_hash(request.form["password"]),
            role=request.form["role"].lower()
        )
        db.session.add(user)
        db.session.commit()

        flash("Account created successfully", "success")
        return redirect("/login")

    return render_template("signup.html")

# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"]).first()

        if user and check_password_hash(user.password, request.form["password"]):
            session.clear()
            session["user_id"] = user.id
            session["role"] = user.role
            session["username"] = user.username

            return redirect(
                "/recruiter/dashboard"
                if user.role == "recruiter"
                else "/seeker/dashboard"
            )

        flash("Invalid credentials", "error")

    return render_template("login.html")

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ================= SEEKER DASHBOARD =================
@app.route("/seeker/dashboard")
def seeker_dashboard():
    if session.get("role") != "seeker":
        return redirect("/login")

    jobs = Job.query.all()
    applications = Application.query.filter_by(
        user_id=session["user_id"]
    ).order_by(Application.id.desc()).all()

    return render_template(
        "seeker_dashboard.html",
        jobs=jobs,
        applications=applications,
        username=session["username"]
    )

# ================= APPLY JOB =================
@app.route("/apply/<int:job_id>", methods=["POST"])
def apply_job(job_id):
    if session.get("role") != "seeker":
        return redirect("/login")

    if Application.query.filter_by(
        job_id=job_id,
        user_id=session["user_id"]
    ).first():
        flash("Already applied", "error")
        return redirect("/seeker/dashboard")

    resume = request.files.get("resume")
    if not resume or not allowed_file(resume.filename):
        flash("Upload valid resume", "error")
        return redirect("/seeker/dashboard")

    filename = secure_filename(resume.filename)
    resume.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

    application = Application(
        job_id=job_id,
        user_id=session["user_id"],
        cover_letter=request.form.get("cover_letter", ""),
        resume=filename,
        status="pending"
    )

    db.session.add(application)
    db.session.commit()

    flash("Application submitted", "success")
    return redirect("/seeker/dashboard")

# ================= RECRUITER DASHBOARD =================
@app.route("/recruiter/dashboard")
def recruiter_dashboard():
    if session.get("role") != "recruiter":
        return redirect("/login")

    jobs = Job.query.filter_by(posted_by=session["user_id"]).all()

    applications = (
        Application.query
        .join(Job)
        .filter(Job.posted_by == session["user_id"])
        .order_by(Application.id.desc())
        .all()
    )

    return render_template(
        "recruiter_dashboard.html",
        jobs=jobs,
        applications=applications,
        username=session["username"]
    )

# ================= POST JOB =================
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

# ================= ACCEPT =================
@app.route("/accept/<int:app_id>", methods=["POST"])
def accept_applicant(app_id):
    if session.get("role") != "recruiter":
        return redirect("/login")

    application = Application.query.get_or_404(app_id)
    application.status = "accepted"
    db.session.commit()

    flash("Applicant accepted", "success")
    return redirect("/recruiter/dashboard")

# ================= REJECT =================
@app.route("/reject/<int:app_id>", methods=["POST"])
def reject_applicant(app_id):
    if session.get("role") != "recruiter":
        return redirect("/login")

    application = Application.query.get_or_404(app_id)
    application.status = "rejected"
    db.session.commit()

    flash("Applicant rejected", "success")
    return redirect("/recruiter/dashboard")

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
