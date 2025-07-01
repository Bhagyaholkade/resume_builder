from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_dance.contrib.google import make_google_blueprint, google
from reportlab.pdfgen import canvas
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "YOUR_SECRET_KEY"

# Session config
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Allow insecure transport for local Google OAuth
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# SQLAlchemy config
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///resume_history.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Google OAuth setup
google_bp = make_google_blueprint(
    client_id="1065495692505-oij449t308l2qpnvd67k962fhs037obr.apps.googleusercontent.com",
    client_secret="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",
    redirect_to="profile"
)
app.register_blueprint(google_bp, url_prefix="/login")

# Ensure resume_pdfs directory exists
if not os.path.exists("resume_pdfs"):
    os.makedirs("resume_pdfs")

# Database model for download history
class ResumeHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(100))
    user_email = db.Column(db.String(150))
    resume_type = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Home page
@app.route("/")
def home():
    user_name = session.get("user_name")
    return render_template("index.html", user_name=user_name)

# Google OAuth profile page
@app.route("/profile")
def profile():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if resp.ok:
        user_info = resp.json()
        session["user_name"] = user_info["name"]
        session["user_email"] = user_info["email"]
        return render_template("profile.html", user=user_info)
    return "Failed to fetch user info."

# Logout route
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# Resume form page redirection
@app.route("/create_resume")
def create_resume_default():
    return redirect(url_for("create_resume", type="normal"))

# Resume form for specified type
@app.route("/create_resume/<type>")
def create_resume(type):
    session["resume_type"] = type
    return render_template("create_resume.html", resume_type=type)

# Resume form submission
@app.route("/generate_resume", methods=["POST"])
def generate_resume():
    resume_data = request.form.to_dict()
    session["resume_data"] = resume_data
    resume_type = session.get("resume_type", "normal")
    return redirect(url_for("payment_page", type=resume_type))

# Payment page route
@app.route("/payment/<type>")
def payment_page(type):
    if type == "ats":
        price, name = 99, "ATS Resume"
    elif type == "premium":
        price, name = 149, "Premium Resume"
    else:
        price, name = 29, "Normal Resume"
    return render_template("payment.html", price=price, resume_type=name, type=type)

# Payment success
@app.route("/payment_success/<type>")
def payment_success(type):
    return render_template("success.html", resume_type=type)

# Helper: Generate PDF resume
def generate_pdf(data, filename):
    pdf_path = os.path.join("resume_pdfs", filename)
    c = canvas.Canvas(pdf_path)
    c.drawString(100, 800, f"Name: {data['name']}")
    c.drawString(100, 780, f"Email: {data['email']}")
    c.drawString(100, 760, f"Phone: {data['phone']}")
    c.drawString(100, 740, f"Summary: {data['summary']}")
    c.drawString(100, 720, f"Skills: {data['skills']}")
    c.drawString(100, 700, f"Degree: {data['degree']} ({data['degree_passout']})")
    c.save()
    return pdf_path

# Resume download route with history logging
@app.route("/download_resume")
def download_resume():
    data = session.get("resume_data")
    if not data:
        return redirect("/")

    history = ResumeHistory(
        user_name=session.get("user_name"),
        user_email=session.get("user_email"),
        resume_type=session.get("resume_type", "Normal Resume")
    )
    db.session.add(history)
    db.session.commit()

    filename = f"{data['name'].replace(' ', '_')}.pdf"
    pdf_path = generate_pdf(data, filename)

    return send_from_directory("resume_pdfs", filename, as_attachment=True)

# View download history
@app.route("/history")
def history():
    if "user_email" not in session:
        return redirect(url_for("google.login"))

    records = ResumeHistory.query.filter_by(user_email=session["user_email"]).all()
    return render_template("history.html", records=records, user_name=session.get("user_name"))

# 404 error handler
@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)

