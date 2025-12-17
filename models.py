from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# ==========================
# User Model
# ==========================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'recruiter' or 'seeker'

    # Relationships
    jobs = db.relationship('Job', backref='poster', lazy=True)
    applications = db.relationship('Application', backref='applicant', lazy=True)


# ==========================
# Job Model
# ==========================
class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    posted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    location = db.Column(db.String(100))  # Optional field for job location

    # Relationships
    applications = db.relationship('Application', backref='job', lazy=True)


# ==========================
# Application Model
# ==========================
class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    cover_letter = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")  # NEW: pending/accepted/rejected
