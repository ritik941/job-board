from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = "user"   # 🔥 THIS LINE FIXES EVERYTHING

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)


class Job(db.Model):
    __tablename__ = "job"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    location = db.Column(db.String(100))
    posted_by = db.Column(db.Integer, db.ForeignKey("user.id"))


class Application(db.Model):
    __tablename__ = "application"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"))
    cover_letter = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")
