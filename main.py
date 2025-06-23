from flask import Flask, render_template, request, redirect, session, url_for, flash
import requests, os
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your-default-dev-key")
WORKER_URL = "http://13.53.193.75:8000"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")


@app.route("/", methods=["GET", "POST"])
def start():
    if request.method == "POST":
        doc_id = request.form.get("google_doc_id")
        create_new = "create_new" in request.form
        num_urls = int(request.form.get("num_urls", 1))
        output_option = request.form.get("output_option", "google_doc")

        session["google_doc_id"] = doc_id
        session["create_new"] = create_new
        session["num_urls"] = num_urls
        session["output_option"] = output_option

        return redirect("/add")

    return render_template("start.html")


@app.route("/add", methods=["GET", "POST"])
def add_post():
    doc_link = None
    post_data = None

    if request.method == "POST":
        urls = request.form.getlist("linkedin_urls")
        if not urls:
            flash("❌ Please enter at least one LinkedIn post URL.", "error")
            return render_template("add_post.html", num_urls=session.get("num_urls", 1))

        show_on_web = session.get("output_option") == "show_on_web"

        payload = {
            "linkedin_urls": urls,
            "google_doc_id": session.get("google_doc_id"),
            "create_new": session.get("create_new", False),
            "show_on_web": show_on_web
        }

        headers = {}
        if not show_on_web:
            creds = session.get("credentials")
            if not creds:
                flash("❌ Missing Google credentials. Please authorize again.", "error")
                return redirect(url_for("authorize"))
            headers = {"Authorization": f"Bearer {creds['access_token']}"}

        try:
            response = requests.post(f"{WORKER_URL}/process", json=payload, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if show_on_web:
                    post_data = data.get("posts", [])
                else:
                    doc_link = data.get("doc_link")
                    flash("✅ Posts added successfully!", "success")
            else:
                flash(f"❌ Error from worker: {response.text}", "error")
        except Exception as e:
            flash(f"❌ Exception during request: {e}", "error")

    return render_template(
        "add_post.html",
        num_urls=session.get("num_urls", 1),
        doc_link=doc_link,
        post_data=post_data
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
