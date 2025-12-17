from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from flask_mail import Mail, Message
from flask_migrate import Migrate
from models import db, User, Job, Application  # Make sure Application has 'status' column

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
migrate = Migrate(app, db)

# Ensure tables exist
with app.app_context():
    db.create_all()
    print("✅ Tables created or verified successfully")
# ===============================================

# ================= UPLOAD FOLDER =================
UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# ===============================================

# ----------------- ROUTES -----------------
# ... keep all your routes here (signup, login, logout, dashboards, apply, accept, reject)
# ✅ Make sure every Message() has 'sender=app.config["MAIL_USERNAME"]'

# ---------- RUN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
