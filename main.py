from flask import Flask, render_template, request, redirect, session, url_for, flash
import requests, os
from urllib.parse import urlencode
from dotenv import load_dotenv
#import subprocess
load_dotenv()
#from flask_session import Session



app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "your-default-dev-key")
app.secret_key = os.getenv("FLASK_SECRET_KEY")
WORKER_URL = os.getenv("WORKER_URL")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

#app.config["SESSION_TYPE"] = "filesystem"
#app.config["SESSION_PERMANENT"] = False
#Session(app)

@app.route("/", methods=["GET", "POST"])
def start():
    if request.method == "POST":
        doc_id = request.form.get("google_doc_id")
        create_new = "create_new" in request.form
        num_urls = int(request.form.get("num_urls", 1))

        session["google_doc_id"] = doc_id
        session["create_new"] = create_new
        session["num_urls"] = num_urls

        return redirect("/add")

    return render_template("start.html")

@app.route("/add", methods=["GET", "POST"])
def add_post():
    doc_link = None

    if request.method == "POST":
        urls = request.form.getlist("linkedin_urls")
        if not urls:
            flash("❌ Please enter at least one LinkedIn post URL.", "error")
            return render_template("add_post.html", num_urls=session.get("num_urls", 1))

        payload = {
            "linkedin_urls": urls,
            "google_doc_id": session.get("google_doc_id"),
            "create_new": session.get("create_new", False)
        }

        creds = session.get("credentials")
        if not creds:
            flash("❌ Missing Google credentials. Please authorize again.", "error")
            return redirect(url_for("authorize"))

        headers = {"Authorization": f"Bearer {creds['access_token']}"}

        try:
            response = requests.post(f"{WORKER_URL}/process", json=payload, headers=headers)
            if response.status_code == 200:
                data = response.json()
                doc_link = data.get("doc_link")
                flash("✅ Posts added successfully!", "success")
            else:
                flash(f"❌ Error from worker: {response.text}", "error")
        except Exception as e:
            flash(f"❌ Exception during request: {e}", "error")

    return render_template(
        "add_post.html",
        num_urls=session.get("num_urls", 1),
        doc_link=doc_link
    )

@app.route("/authorize")
def authorize():
    query = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/documents https://www.googleapis.com/auth/drive.file",
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = f"https://accounts.google.com/o/oauth2/auth?{urlencode(query)}"
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    code = request.args.get("code")
    if not code:
        flash("❌ Authorization failed. No code returned.", "error")
        return redirect(url_for("start"))

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        session["credentials"] = response.json()
        flash("✅ Google authorization successful!", "success")
    except requests.RequestException as e:
        flash(f"❌ Failed to obtain access token: {e}", "error")
        return redirect(url_for("start"))

    return redirect(url_for("start"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

