from datetime import datetime, timedelta
from functools import wraps
import hashlib
import hmac
import ipaddress
import json
import json
import math
import os
import os
import re
import secrets
import string
import subprocess
import urllib.parse
import urllib.request
import urllib.request

from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask import render_template
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from google_auth_oauthlib.flow import Flow
from itsdangerous import URLSafeTimedSerializer
import requests
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from known_bots import detect_bot, verify_bot_ip
from mailer import send_mail
from mailer import mail
from models import (
    Admin,
    BlockedIP,
    Comment,
    Inquiry,
    Project,
    ProjectImage,
    ProjectVideo,
    Registration,
    RequestLog,
    ProjectFile,
    Service,
    Testimonial,
    User,
    db,
)

app = Flask(__name__)
COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE","0")=="1"

app.config.update(
    MAX_CONTENT_LENGTH=25*1024*1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=COOKIE_SECURE,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=72),
    SECRET_KEY=os.getenv("FLASK_SECRET","secret-key"),
    SQLALCHEMY_DATABASE_URI="sqlite:///ogwenofaya.db",
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAIL_SERVER="mail.tunupublishers.com",
    MAIL_PORT=465,
    MAIL_USE_SSL=True,
    MAIL_USE_TLS=False,
    MAIL_USERNAME="library@tunupublishers.com",
    MAIL_PASSWORD=os.getenv("MAIL_PASS"),
    MAIL_DEFAULT_SENDER="library@tunupublishers.com"
)
RECAPTCHA_SECRET_KEY = os.getenv('RECAPTCHA_SECRET_KEY')


ADMIN_EMAILS = [
    email.strip().lower()
    for email in os.getenv("ADMIN_EMAILS", "").split(",")
    if email.strip()
]

delta = 3

db.init_app(app)
mail.init_app(app)


SENDER_MAIL = "library@tunupublishers.com"


def captcha_verify(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if request.method == "POST":
            if request.form.get("website_url"):
                if (
                    request.is_json
                    or request.headers.get("Accept") == "application/json"
                ):
                    return jsonify({"error": "Invalid request."}), 400
                flash("Please complete the reCAPTCHA checkbox verification.", "error")
                return redirect(request.referrer or "/")

            token = request.form.get("g-recaptcha-response")

            if not token:
                if (
                    request.is_json
                    or request.headers.get("Accept") == "application/json"
                    or request.headers.get("X-Requested-With") == "XMLHttpRequest"
                ):
                    return jsonify(
                        {"error": "Please complete the reCAPTCHA verification."}
                    ), 400
                flash("Please complete the reCAPTCHA checkbox verification.", "error")
                return redirect(request.referrer or "/")

            try:
                result = requests.post(
                    "https://www.google.com/recaptcha/api/siteverify",
                    data={
                        "secret": RECAPTCHA_SECRET_KEY,
                        "response": token,
                        "remoteip": request.remote_addr,
                    },
                    timeout=10,
                ).json()
            except requests.RequestException:
                if (
                    request.is_json
                    or request.headers.get("Accept") == "application/json"
                    or request.headers.get("X-Requested-With") == "XMLHttpRequest"
                ):
                    return jsonify(
                        {"error": "reCAPTCHA verification failed. Please try again."}
                    ), 400
                flash("reCAPTCHA verification failed. Please try again.", "error")
                return redirect(request.referrer or "/")

            if not result.get("success"):
                if (
                    request.is_json
                    or request.headers.get("Accept") == "application/json"
                    or request.headers.get("X-Requested-With") == "XMLHttpRequest"
                ):
                    return jsonify(
                        {"error": "Please complete the reCAPTCHA verification."}
                    ), 400
                flash("Please complete the reCAPTCHA checkbox verification.", "error")
                return redirect(request.referrer or "/")

        return f(*args, **kwargs)

    return wrapper


app.config["MAIL_DEFAULT_SENDER"] = (
    "OgwenofayaVisuals",
     f'{SENDER_MAIL}'
)

migrate = Migrate(app, db)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)


def create_reg():
    ex_reg = Registration.query.first()
    if ex_reg:
        return ex_reg

    new_reg = Registration(status=False)
    db.session.add(new_reg)
    db.session.commit()
    return new_reg



    
with app.app_context():
    create_reg()
    



IMAGE_DIR = os.path.join(app.root_path, "static", "resources", "images")
VIDEO_DIR = os.path.join(app.root_path, "static", "resources", "videos")
FILES_DIR = os.path.join(app.root_path, "static", "resources", "files")
GOOGLE_CLIENT_SECRETS_FILE="client_secret.json"
os.environ["OAUTHLIB_INSECURE_TRANSPORT"]="1"

SCOPES=[
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]
delta = 3

os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(FILES_DIR, exist_ok=True)

def generate_token(user_id,tkv):
    return hmac.new(
        app.secret_key.encode(),
        f"{user_id}:{tkv}".encode(),
        hashlib.sha256
    ).hexdigest()

def gen_id(prefix, len=8):
    chars = string.digits + string.ascii_letters
    return prefix + "".join(secrets.choice(chars) for _ in range(len))

def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-')

def unique_slug(title, exclude_id=None):
    base_slug = slugify(title)
    if not base_slug:
        base_slug = "project"
    slug = base_slug
    counter = 1
    while True:
        query = Project.query.filter_by(slug=slug)
        if exclude_id:
            query = query.filter(Project.id != exclude_id)
        if not query.first():
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1

def save_upload(file, folder, prefix):
    if not file or not file.filename:
        return None
    filename = secure_filename(file.filename)
    ext = os.path.splitext(filename)[1].lower()
    if not ext:
        return None
    filename = f"{gen_id(prefix)}{ext}"
    file.save(os.path.join(folder, filename))
    return filename

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp", ".tif", ".tiff"}

def save_image_upload(file):
    if not file or not file.filename:
        return None
    ext = os.path.splitext(secure_filename(file.filename))[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        return None
    return save_upload(file, IMAGE_DIR, "IMG_")



def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        admin = Admin.query.filter_by(id=session.get("admin_id")).first()
        if not admin:
            flash("Please login to continue", "error")
            session.clear()
            return redirect(url_for("login")) 
        if not admin.is_active:
            flash("Account Inactive. Please contact support", "error")
            return redirect(url_for("login")) 
        return f(*args, **kwargs)
    return wrapper


def get_location_by_ip(ip):
    if not ip:
        return {"status": "error", "location": "Unknown"}

    try:
        ip_obj = ipaddress.ip_address(ip)

        if ip_obj.is_loopback:
            return {
                "status": "local",
                "ip": ip,
                "location": "Localhost"
            }

        if not ip_obj.is_global:
            return {
                "status": "private",
                "ip": ip,
                "location": "Private Network"
            }

        fields = ",".join([
            "status", "message", "query",
            "continent", "continentCode",
            "country", "countryCode",
            "region", "regionName",
            "city", "district", "zip",
            "lat", "lon", "timezone", "offset",
            "currency", "isp", "org", "as",
            "asname", "reverse",
            "mobile", "proxy", "hosting"
        ])

        url = (
            f"http://ip-api.com/json/"
            f"{urllib.parse.quote(str(ip_obj), safe='')}"
            f"?fields={fields}"
        )

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())

        if data.get("status") != "success":
            return {
                "status": "error",
                "ip": ip,
                "location": "Unknown",
                "message": data.get("message")
            }

        return {
            "status": "success",
            "ip": data.get("query"),
            "location": ", ".join(filter(None, [
                data.get("district"),
                data.get("city"),
                data.get("regionName"),
                data.get("country")
            ])),
            "continent": data.get("continent"),
            "continent_code": data.get("continentCode"),
            "country": data.get("country"),
            "country_code": data.get("countryCode"),
            "region": data.get("regionName"),
            "region_code": data.get("region"),
            "city": data.get("city"),
            "district": data.get("district"),
            "postal_code": data.get("zip"),
            "latitude": data.get("lat"),
            "longitude": data.get("lon"),
            "timezone": data.get("timezone"),
            "utc_offset": data.get("offset"),
            "currency": data.get("currency"),
            "isp": data.get("isp"),
            "organization": data.get("org"),
            "asn": data.get("as"),
            "asn_name": data.get("asname"),
            "hostname": data.get("reverse"),
            "is_mobile": data.get("mobile"),
            "is_proxy": data.get("proxy"),
            "is_hosting": data.get("hosting")
        }

    except Exception:
        return {
            "status": "error",
            "ip": ip,
            "location": "Unknown"
        }

@app.context_processor
def globals():
    reg = Registration.query.first()

    return {
        "site_name": "OgwenofayaVisuals",
        "year": datetime.utcnow().year,
        "r_b": bool(reg and reg.status)
    }

@app.after_request
def log_request(response):
    paths = [
        "/json/version",
        "/.well-known/appspecific/com.chrome.devtools.json",
        "/favicon.ico"
    ]

    if request.path.startswith(('/static/', '/video/')) or request.path in paths:
        return response

    sa = session.get('is_super_admin')
    li = session.get('username')
    pref = ''

    if sa:
        pref = f'[ISADM] : {session.get("username")} &bull; '

    if li and not sa:
        pref = f"{li} &bull; "

    try:
        ua = request.user_agent.string
        ip = request.remote_addr

        is_bot, bot_name = detect_bot(ua)
        verified = False
        hostname = None

        if is_bot:
            verified, verified_name, hostname = verify_bot_ip(ip, ua)

            if verified:
                bot_name = verified_name

        location = get_location_by_ip(ip)

        log_entry = RequestLog(
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            ip_address=ip,
            location=location.get("location"),
            user_agent=pref + ua[:255],
            is_bot=is_bot,
            bot_name=bot_name
        )

        db.session.add(log_entry)
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"Logging error: {e}", flush=True)

    return response

def is_ip_blocked(ip):
    return BlockedIP.query.filter_by(ip_address=ip).first() is not None

def block_ip(ip):
    if not is_ip_blocked(ip):
        db.session.add(BlockedIP(ip_address=ip))
        db.session.commit()
        return True
    return False

@app.route("/")
def index():
    projects = Project.query.filter_by(is_deleted=False).order_by(Project.created_at.desc()).all()
    featured = Project.query.filter_by(featured=True, is_deleted=False).order_by(Project.created_at.desc()).all()
    services = Service.query.filter_by(is_deleted=False).order_by(Service.position.asc()).all()
    testimonials = Testimonial.query.filter_by(is_deleted=False).order_by(Testimonial.position.asc()).all()
    return render_template(
        "index.html",
        projects=projects,
        featured=featured,
        services=services,
        testimonials=testimonials
    )

@app.route("/work/<slug>")
def project(slug):
    project = Project.query.filter_by(slug=slug, is_deleted=False).first_or_404()
    related_projects = (
        Project.query
        .filter(Project.id != project.id, Project.is_deleted == False)
        .order_by(Project.created_at.desc())
        .limit(6)
        .all()
    )
    return render_template(
        "project.html",
        project=project,
        related_projects=related_projects
    )

if os.name=="nt":
    FFMPEG=os.environ.get("FFMPEG","ffmpeg")
else:
    FFMPEG=os.environ.get("FFMPEG","/home3/tunujournl/repositories/ogwenofaya-visuals/bin/ffmpeg")
    
    
def checkProcess():
    try:
        subprocess.run([FFMPEG, "-version"], check=True, capture_output=True, text=True)
    except Exception as e:
        print(f"FFmpeg error: {e}", flush=True)

@app.post("/contact")
@captcha_verify
@limiter.limit("5 per minute")
def contact():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    service = request.form.get("service", "").strip()
    message = request.form.get("message", "").strip()
    if not name or not email or not message:
        flash("Please complete the required fields.")
        return redirect(url_for("index") + "#contact")
    inquiry = Inquiry(
        name=name,
        email=email,
        phone=phone,
        service=service,
        message=message
    )
    db.session.add(inquiry)
    db.session.commit()
    flash("Your enquiry has been received.")
    return redirect(url_for("index") + "#contact")

@app.route("/register", methods=["GET", "POST"])
@limiter.limit("50 per minute")
@captcha_verify
def register():
    r = Registration.query.first()
    
    if not r:
        create_reg()
    
    if not r.status:
        return redirect(url_for('login'))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        if Admin.query.filter_by(username=username).first():
            flash("An account with that username already exists.", "error")
            return render_template("register.html")

        if Admin.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return render_template("register.html")

        admin = Admin(
            username=username,
            email=email,
            password=generate_password_hash(password),
            email_method=True,
            is_admin=True,
            is_super_admin=False,
            is_active=False
        )

        db.session.add(admin)
        db.session.commit()

        token = serializer.dumps(admin.id, salt="register-account")
        auth_url = url_for("authorize_account", token=token, _external=True)

        for e in ADMIN_EMAILS:
            adm = Admin.query.filter_by(email=e).first()

            if adm:
                email_html = f"""
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#f8fafc;padding:30px 0;font-family:'Manrope',Arial,sans-serif;">
    <tr>
        <td align="center">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;border:1px solid #d8e2ed;box-shadow:0 10px 30px rgba(7,13,22,0.05);overflow:hidden;">
                <tr>
                    <td style="padding:36px;">
                        <h2 style="margin:0 0 16px 0;color:#070d16;font-size:20px;font-weight:800;letter-spacing:-0.02em;">Confirm Account Creation</h2>

                        <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 14px 0;">A request was made to create an admin account using:</p>

                        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;margin-bottom:16px;">
                            <tr>
                                <td style="padding:12px 16px;font-size:15px;color:#0f172a;font-weight:700;">
                                    {admin.email}
                                </td>
                            </tr>
                        </table>

                        <p style="color:#475569;font-size:14px;margin:0 0 24px 0;">
                            <strong style="color:#0f172a;">Username:</strong> {admin.username}
                        </p>

                        <h3 style="color:#070d16;font-size:13px;font-weight:800;text-transform:uppercase;letter-spacing:0.08em;margin:0 0 12px 0;border-top:1px solid #e2e8f0;padding-top:20px;">Location & Device Details</h3>

                        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;margin-bottom:24px;">
                            <tr>
                                <td style="padding:10px 16px;border-bottom:1px solid #e2e8f0;color:#64748b;font-size:12px;font-weight:700;width:30%;">Device</td>
                                <td style="padding:10px 16px;border-bottom:1px solid #e2e8f0;color:#0f172a;font-size:13px;">{request.user_agent}</td>
                            </tr>
                            <tr>
                                <td style="padding:10px 16px;border-bottom:1px solid #e2e8f0;color:#64748b;font-size:12px;font-weight:700;">IP Address</td>
                                <td style="padding:10px 16px;border-bottom:1px solid #e2e8f0;color:#0f172a;font-size:13px;">{request.remote_addr}</td>
                            </tr>
                            <tr>
                                <td style="padding:10px 16px;border-bottom:1px solid #e2e8f0;color:#64748b;font-size:12px;font-weight:700;">Location</td>
                                <td style="padding:10px 16px;border-bottom:1px solid #e2e8f0;color:#0f172a;font-size:13px;">{get_location_by_ip(request.remote_addr)}</td>
                            </tr>
                            <tr>
                                <td style="padding:10px 16px;color:#64748b;font-size:12px;font-weight:700;">Time</td>
                                <td style="padding:10px 16px;color:#0f172a;font-size:13px;">{datetime.utcnow() + timedelta(hours=3)}</td>
                            </tr>
                        </table>

                        <p style="margin:0 0 16px 0;color:#0f172a;font-weight:600;font-size:14px;">
                            Do you want to authorize this account?
                        </p>

                        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">
                            <tr>
                                <td align="center" style="border-radius:10px;background-color:#368bff;">
                                    <a href="{auth_url}" target="_blank" style="display:inline-block;padding:12px 24px;font-family:'Manrope',Arial,sans-serif;font-size:13px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:10px;background-color:#368bff;box-shadow:0 4px 12px rgba(54,139,255,0.25);">
                                        Review Request &rarr;
                                    </a>
                                </td>
                            </tr>
                        </table>

                        <p style="margin:0;font-size:12px;color:#64748b;border-top:1px solid #e2e8f0;padding-top:16px;line-height:1.5;">
                            This security link expires in 30 minutes. If you did not initiate this request, you can safely ignore this email.
                        </p>
                    </td>
                </tr>
            </table>
        </td>
    </tr>
</table> """

                send_mail(adm.id, "Account Confirmation", email_html)

        flash("Admin account created. Authorization is required before you can login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route('/control/ip/block', methods=['POST'])
@admin_required
def block_req_ip():
    my_ip = request.remote_addr
    data = request.get_json()
    id = data.get("id")
    ip = ''
    log = RequestLog.query.filter_by(id=id).first()
    if log:
        ip = log.ip_address
    if ip == my_ip:
        return jsonify({'error': "Oops... You can not block your own IP"}), 400
    if block_ip(ip):
        return jsonify({'success':'IP blocked successfully'})
    else:
        return jsonify({'error':'Failed to block IP'})
    
    

@app.route("/authorize-account/<token>")
def authorize_account(token):
    try:
        admin_id = serializer.loads(
            token,
            salt="register-account",
            max_age=1800
        )
    except Exception:
        return render_template(
            "admin/authorize_account.html",
            expired=True
        )

    admin = Admin.query.get(admin_id)

    if not admin:
        return render_template(
            "admin/authorize_account.html",
            expired=True
        )

    if admin.is_active:
        return render_template(
            "admin/authorize_account.html",
            already_authorized=True,
            admin=admin
        )

    return render_template(
        "admin/authorize_account.html",
        admin=admin,
        token=token
    )


@app.route("/authorize-account/<token>/yes", methods=["POST"])
def authorize_account_yes(token):
    try:
        admin_id = serializer.loads(
            token,
            salt="register-account",
            max_age=1800
        )
    except Exception:
        return render_template(
            "admin/authorize_account.html",
            expired=True
        )

    admin = Admin.query.get(admin_id)

    if not admin:
        return render_template(
            "admin/authorize_account.html",
            expired=True
        )

    if admin.is_active:
        return render_template(
            "admin/authorize_account.html",
            already_authorized=True,
            admin=admin
        )

    admin.is_active = True
    db.session.commit()
    
    email_html = f"""
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#f8fafc;padding:30px 0;font-family:'Plus Jakarta Sans',Arial,sans-serif;">
        <tr>
            <td align="center">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;border:1px solid #cbd5e1;box-shadow:0 4px 20px rgba(15,23,42,0.06);overflow:hidden;">
                    <tr>
                        <td style="padding:36px;">
                            <h2 style="margin:0 0 16px 0;color:#0f172a;font-size:20px;font-weight:800;letter-spacing:-0.02em;">Account Authorized</h2>
                            
                            <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 20px 0;">
                                Great news! Your administrator registration request for <strong style="color:#0f172a;">OgwenofayaVisuals</strong> has been reviewed and approved by management.
                            </p>

                            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;margin-bottom:24px;">
                                <tr>
                                    <td style="padding:14px 18px;font-size:13px;color:#475569;">
                                        <strong style="color:#0f172a;display:block;margin-bottom:4px;text-transform:uppercase;font-size:11px;letter-spacing:0.05em;">Assigned Username</strong>
                                        {admin.username}
                                    </td>
                                </tr>
                            </table>

                            <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">
                                <tr>
                                    <td align="center" style="border-radius:6px;background-color:#2563eb;">
                                        <a href="{url_for('login', _external=True)}" target="_blank" style="display:inline-block;padding:12px 24px;font-family:'Plus Jakarta Sans',Arial,sans-serif;font-size:13px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:6px;background-color:#2563eb;">
                                            Sign In to Control Center &rarr;
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin:0;font-size:12px;color:#64748b;border-top:1px solid #e2e8f0;padding-top:16px;line-height:1.5;">
                                If you did not make this request or have any questions, please contact your studio administrator immediately.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>    
"""
    
    send_mail(admin.id, "Account Verified", email_html)
    print('mail sent', admin.id, "Account Verified", email_html)

    return render_template(
        "admin/authorize_account.html",
        authorized=True,
        admin=admin
    )


@app.route("/authorize-account/<token>/no", methods=["POST"])
def authorize_account_no(token):
    try:
        admin_id = serializer.loads(
            token,
            salt="register-account",
            max_age=1800
        )
    except Exception:
        return render_template(
            "admin/authorize_account.html",
            expired=True
        )

    admin = Admin.query.get(admin_id)

    if not admin:
        return render_template(
            "admin/authorize_account.html",
            expired=True
        )

    if admin.is_active:
        return render_template(
            "admin/authorize_account.html",
            already_authorized=True,
            admin=admin
        )

    db.session.delete(admin)
    db.session.commit()

    return render_template(
        "admin/authorize_account.html",
        rejected=True
    )
    

@app.route("/login", methods=["GET", "POST"])
@captcha_verify
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password, password):
            session["admin"] = True
            if admin.is_super_admin:
                session["is_super_admin"] = True
            session["admin_id"] = admin.id
            session["username"] = admin.username
            return redirect(url_for("control"))
        flash("Invalid username or password.", 'error')
    return render_template("login.html")

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/control")
@admin_required
def control():
    ten_days_ago = datetime.utcnow() - timedelta(days=10)
    daily_logs_raw = (
        db.session.query(
            func.date(RequestLog.created_at).label("log_date"),
            func.count(RequestLog.id).label("count")
        )
        .filter(RequestLog.created_at >= ten_days_ago, RequestLog.is_deleted == False)
        .group_by(func.date(RequestLog.created_at))
        .all()
    )
    
    log_counts_map = {str(row.log_date): row.count for row in daily_logs_raw}
    chart_data = []
    max_log_count = 1
    for i in range(9, -1, -1):
        d = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        label = (datetime.utcnow() - timedelta(days=i)).strftime("%b %d")
        cnt = log_counts_map.get(d, 0)
        chart_data.append({"label": label, "count": cnt})
        if cnt > max_log_count:
            max_log_count = cnt

    top_slugs_raw = (
        db.session.query(RequestLog.path, func.count(RequestLog.id).label("opens"))
        .filter(RequestLog.path.like("/work/%"), RequestLog.is_deleted == False)
        .group_by(RequestLog.path)
        .order_by(func.count(RequestLog.id).desc())
        .limit(5)
        .all()
    )
    
    top_projects = []
    max_project_opens = 1
    for path, opens in top_slugs_raw:
        slug = path.split("/")[-1]
        proj = Project.query.filter_by(slug=slug, is_deleted=False).first()
        if proj:
            top_projects.append({"title": proj.title, "opens": opens})
            if opens > max_project_opens:
                max_project_opens = opens

    return render_template(
        "admin/dashboard.html",
        projects=Project.query.filter_by(is_deleted=False).order_by(Project.created_at.desc()).all(),
        services=Service.query.filter_by(is_deleted=False).order_by(Service.position.asc()).all(),
        testimonials=Testimonial.query.filter_by(is_deleted=False).order_by(Testimonial.position.asc()).all(),
        inquiries=Inquiry.query.filter_by(is_deleted=False).order_by(Inquiry.created_at.desc()).all(),
        chart_data=chart_data,
        max_log_count=max_log_count,
        top_projects=top_projects,
        max_project_opens=max_project_opens
    )

def admin_form_response(message, ok=True, status=200):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(ok=ok, message=message), status
    flash(message)
    return redirect(url_for("control"))

@app.post("/control/projects/file/delete/<int:file_id>")
@admin_required
def delete_project_file(file_id):
    file_record = ProjectFile.query.get_or_404(file_id)
    project_id = file_record.project_id
    path = os.path.join(IMAGE_DIR, file_record.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(file_record)
    db.session.commit()
    flash("File deleted from project.")
    return redirect(url_for("edit_project", id=project_id))


@app.post("/control/project")
@admin_required
def add_project():
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    if not title or not category:
        flash("Title and category are required.", 'error')
        return redirect(url_for('projects_page'))
    
    slug = unique_slug(title)
    
    uploaded_files = request.files.getlist("images")
    if not any(file and file.filename for file in uploaded_files):
        legacy_file = request.files.get("image")
        uploaded_files = [legacy_file] if legacy_file and legacy_file.filename else []
    
    saved_images = []
    saved_videos = []
    saved_files = []
    
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp", ".tif", ".tiff"}
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
    
    for file in uploaded_files:
        if not file or not file.filename:
            continue
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()
        if not ext:
            continue
        
        if ext in IMAGE_EXTENSIONS:
            saved_name = f"{gen_id('IMG_')}{ext}"
            file.save(os.path.join(IMAGE_DIR, saved_name))
            saved_images.append(saved_name)
        elif ext in VIDEO_EXTENSIONS:
            saved_name = f"{gen_id('VID_')}{ext}"
            file.save(os.path.join(VIDEO_DIR, saved_name))
            saved_videos.append(saved_name)
        else:
            saved_name = f"{gen_id('DOC_')}{ext}"
            file.save(os.path.join(IMAGE_DIR, saved_name))
            saved_files.append(saved_name)

    # Create the project instance
    project = Project(
        title=title,
        slug=slug,
        category=category,
        description=description,
        image=saved_images[0] if saved_images else None,
        video=saved_videos[0] if saved_videos else None,
        featured=request.form.get("featured") == "on"
    )
    db.session.add(project)
    db.session.flush()
    
    for filename in saved_images:
        db.session.add(ProjectImage(project_id=project.id, filename=filename))
    for filename in saved_videos:
        db.session.add(ProjectVideo(project_id=project.id, filename=filename))
    for filename in saved_files:
        db.session.add(ProjectFile(project_id=project.id, filename=filename))
        
    db.session.commit()
    flash('Project created successfully', 'success')
    return redirect(url_for('projects_page'))


@app.post("/control/service")
@admin_required
def add_service():
    service = Service(
        title=request.form.get("title", "").strip(),
        description=request.form.get("description", "").strip(),
        position=int(request.form.get("position", 0) or 0)
    )
    db.session.add(service)
    db.session.commit()
    return redirect(url_for("control"))

FFPROBE = os.environ.get("FFPROBE", "ffprobe")
_VIDEO_DURATION_CACHE = {}

def probe_video_duration(path):
    try:
        modified = os.stat(path).st_mtime_ns
        key = (path, modified)
        if key in _VIDEO_DURATION_CACHE:
            return _VIDEO_DURATION_CACHE[key]
        result = subprocess.run(
            [
                FFPROBE,
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        duration = float(result.stdout.strip())
        if not math.isfinite(duration) or duration <= 0:
            return None
        _VIDEO_DURATION_CACHE[key] = duration
        return duration
    except (OSError, ValueError, subprocess.SubprocessError):
        return None

@app.route("/video/<id>/<int:quality>")
@limiter.exempt
def stream_video(id, quality):
    project = Project.query.get_or_404(id)
    if not project.video:
        return "Video unavailable", 404
    if quality not in [144, 240, 360, 480, 720, 1080]:
        return "Invalid quality", 400
    path = os.path.join(VIDEO_DIR, project.video)
    if not os.path.isfile(path):
        return "Video file not found", 404
    try:
        start = float(request.args.get("start", "0"))
    except (TypeError, ValueError):
        return "Invalid start time", 400
    if not math.isfinite(start) or start < 0 or start > 86400:
        return "Invalid start time", 400
    duration = probe_video_duration(path)
    if duration is not None:
        start = min(start, max(0.0, duration - 0.05))
    command = [FFMPEG, "-hide_banner", "-loglevel", "error"]

    if start>0:
        command += ["-ss",f"{start:.3f}"]

    command += [
        "-i",path,
        "-map","0:v:0",
        "-map","0:a?",
        "-vf",f"scale=-2:min({quality}\\,ih)",
        "-c:v","libx264",
        "-threads","1",
        "-preset","ultrafast",
        "-crf","23",
        "-pix_fmt","yuv420p",
        "-c:a","aac",
        "-b:a","128k",
        "-movflags","frag_keyframe+empty_moov+default_base_moof",
        "-f","mp4",
        "pipe:1",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    def generate():
        try:
            while True:
                chunk = process.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            if process.stdout:
                process.stdout.close()
            if process.poll() is None:
                process.kill()
            process.wait()
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "X-Stream-Start": f"{start:.3f}",
    }
    if duration is not None:
        headers["X-Video-Duration"] = f"{duration:.3f}"
    return Response(generate(), mimetype="video/mp4", headers=headers)


@app.route("/control/testimonials/new", methods=["GET", "POST"])
def add_testimonial_page():
    if not session.get("admin"):
        return redirect(url_for("login"))
    if request.method == "POST":
        name = request.form.get("name")
        company = request.form.get("company")
        quote = request.form.get("quote")
        position = int(request.form.get("position", 0))
        new_testimonial = Testimonial(name=name, company=company, quote=quote, position=position)
        db.session.add(new_testimonial)
        db.session.commit()
        flash("Testimonial added successfully.")
        return redirect(url_for("control"))
    return render_template("admin/add_testimonial.html")

@app.post("/control/delete/project/<id>")
@admin_required
def delete_project(id):
    project = Project.query.get_or_404(id)
    project.is_deleted = True
    db.session.commit()
    flash("Project moved to cache.")
    return redirect(url_for("projects_page"))

@app.post("/control/delete/service/<id>")
@admin_required
def delete_service(id):
    service = Service.query.get_or_404(id)
    service.is_deleted = True
    db.session.commit()
    flash("Service moved to cache.")
    return redirect(url_for("services_page"))

@app.post("/control/delete/testimonial/<id>")
@admin_required
def delete_testimonial(id):
    testimonial = Testimonial.query.get_or_404(id)
    testimonial.is_deleted = True
    db.session.commit()
    flash("Testimonial moved to cache.")
    return redirect(url_for("testimonials_page"))

@app.post("/control/delete/inquiry/<id>")
@admin_required
def delete_inquiry(id):
    inquiry = Inquiry.query.get_or_404(id)
    inquiry.is_deleted = True
    db.session.commit()
    flash("Enquiry moved to cache.")
    return redirect(url_for("messages_page"))

@app.route("/control/cache")
@admin_required
def cache_page():
    deleted_projects = Project.query.filter_by(is_deleted=True).all()
    deleted_services = Service.query.filter_by(is_deleted=True).all()
    deleted_testimonials = Testimonial.query.filter_by(is_deleted=True).all()
    deleted_logs = RequestLog.query.order_by(RequestLog.created_at.desc()).limit(100).all()
    return render_template(
        "admin/cache.html",
        deleted_projects=deleted_projects,
        deleted_services=deleted_services,
        deleted_testimonials=deleted_testimonials,
        deleted_logs=deleted_logs
    )

@app.post("/control/cache/restore/<item_type>/<id>")
@admin_required
def restore_item(item_type, id):
    if item_type == "project":
        item = Project.query.get_or_404(id)
    elif item_type == "service":
        item = Service.query.get_or_404(id)
    elif item_type == "testimonial":
        item = Testimonial.query.get_or_404(id)
    else:
        return "Invalid type", 400
    item.is_deleted = False
    db.session.commit()
    flash("Item restored successfully.")
    return redirect(url_for("cache_page"))

@app.route("/toggle-registration", methods=["POST"])
@admin_required
def toggle_registration():
    reg = create_reg()
    reg.status = not reg.status
    db.session.commit()

    return jsonify(success=True, status=bool(reg.status))

@app.post("/control/cache/purge/<item_type>/<id>")
@admin_required
def purge_item(item_type, id):
    if item_type == "project":
        item = Project.query.get_or_404(id)
        image_filenames = {image.filename for image in item.images}
        if item.image:
            image_filenames.add(item.image)
        for filename in image_filenames:
            path = os.path.join(IMAGE_DIR, filename)
            if os.path.exists(path):
                os.remove(path)
        if item.video:
            path = os.path.join(VIDEO_DIR, item.video)
            if os.path.exists(path):
                os.remove(path)
        db.session.delete(item)
    elif item_type == "service":
        item = Service.query.get_or_404(id)
        db.session.delete(item)
    elif item_type == "testimonial":
        item = Testimonial.query.get_or_404(id)
        db.session.delete(item)
    elif item_type == "log":
        item = RequestLog.query.get_or_404(id)
        db.session.delete(item)
    db.session.commit()
    flash("Item permanently deleted.")
    return redirect(url_for("cache_page"))

@app.cli.command("initdb")
def initdb():
    db.create_all()
    print("Database initialized.")

@app.route("/control/projects/new")
def add_project_page():
    if not session.get("admin"):
        return redirect(url_for("login"))
    return render_template("admin/add_project.html")

@app.route("/control/services/new")
def add_service_page():
    if not session.get("admin"):
        return redirect(url_for("login"))
    return render_template("admin/add_service.html")

@app.route("/control/messages")
def messages_page():
    if not session.get("admin"):
        return redirect(url_for("login"))
    inquiries = Inquiry.query.filter_by(is_deleted=False).order_by(Inquiry.created_at.desc()).all()
    return render_template("admin/messages.html", inquiries=inquiries)

@app.route("/control/projects")
@admin_required
def projects_page():
    projects = Project.query.filter_by(is_deleted=False).order_by(Project.created_at.desc()).all()
    return render_template("admin/projects.html", projects=projects)

@app.route("/control/services")
@admin_required
def services_page():
    services = Service.query.filter_by(is_deleted=False).order_by(Service.position.asc()).all()
    return render_template("admin/services.html", services=services)

@app.route("/control/testimonials")
@admin_required
def testimonials_page():
    testimonials = Testimonial.query.filter_by(is_deleted=False).order_by(Testimonial.position.asc()).all()
    return render_template("admin/testimonials.html", testimonials=testimonials)

@app.route("/control/projects/edit/<string:id>", methods=["GET", "POST"])
def edit_project(id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    project = Project.query.get_or_404(id)
    if request.method == "POST":
        title = request.form.get("title")
        project.title = title
        project.slug = unique_slug(title, exclude_id=project.id)
        project.category = request.form.get("category")
        project.description = request.form.get("description")
        project.featured = True if request.form.get("featured") else False
        
        uploaded_files = request.files.getlist("images")
        if not any(file and file.filename for file in uploaded_files):
            legacy_file = request.files.get("image")
            uploaded_files = [legacy_file] if legacy_file and legacy_file.filename else []
            
        saved_images = []
        saved_videos = []
        saved_files = []
        
        IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp", ".tif", ".tiff"}
        VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
        
        for file in uploaded_files:
            if not file or not file.filename:
                continue
            filename = secure_filename(file.filename)
            ext = os.path.splitext(filename)[1].lower()
            if not ext:
                continue
            
            if ext in IMAGE_EXTENSIONS:
                saved_name = f"{gen_id('IMG_')}{ext}"
                file.save(os.path.join(IMAGE_DIR, saved_name))
                saved_images.append(saved_name)
            elif ext in VIDEO_EXTENSIONS:
                saved_name = f"{gen_id('VID_')}{ext}"
                file.save(os.path.join(VIDEO_DIR, saved_name))
                saved_videos.append(saved_name)
            else:
                saved_name = f"{gen_id('DOC_')}{ext}"
                file.save(os.path.join(FILES_DIR, saved_name))
                saved_files.append(saved_name)
                
        if saved_images:
            if not project.image:
                project.image = saved_images[0]
            for filename in saved_images:
                db.session.add(ProjectImage(project_id=project.id, filename=filename))

        if saved_videos:
            if not project.video:
                project.video = saved_videos[0]
            for filename in saved_videos:
                db.session.add(ProjectVideo(project_id=project.id, filename=filename))
                
        for filename in saved_files:
            db.session.add(ProjectFile(project_id=project.id, filename=filename))

        db.session.commit()
        flash("Project updated successfully.")
        return render_template("admin/edit_project.html", project=project)
    return render_template("admin/edit_project.html", project=project)

@app.post("/control/projects/video/delete/<int:video_id>")
@admin_required
def delete_project_video(video_id):
    vid_record = ProjectVideo.query.get_or_404(video_id)
    project_id = vid_record.project_id
    path = os.path.join(VIDEO_DIR, vid_record.filename)
    if os.path.exists(path):
        os.remove(path)
    project = Project.query.get(project_id)
    if project.video == vid_record.filename:
        other_vid = ProjectVideo.query.filter(ProjectVideo.project_id == project_id, ProjectVideo.id != video_id).first()
        project.video = other_vid.filename if other_vid else None
    db.session.delete(vid_record)
    db.session.commit()
    flash("Video deleted from project.")
    return redirect(url_for("edit_project", id=project_id))

@app.post("/control/projects/image/delete/<int:image_id>")
@admin_required
def delete_project_image(image_id):
    img_record = ProjectImage.query.get_or_404(image_id)
    project_id = img_record.project_id
    path = os.path.join(IMAGE_DIR, img_record.filename)
    if os.path.exists(path):
        os.remove(path)
    project = Project.query.get(project_id)
    if project.image == img_record.filename:
        other_img = ProjectImage.query.filter(ProjectImage.project_id == project_id, ProjectImage.id != image_id).first()
        project.image = other_img.filename if other_img else None
    db.session.delete(img_record)
    db.session.commit()
    flash("Image deleted from project.")
    return redirect(url_for("edit_project", id=project_id))

@app.route("/control/services/edit/<string:id>", methods=["GET", "POST"])
def edit_service(id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    service = Service.query.get_or_404(id)
    if request.method == "POST":
        service.title = request.form.get("title")
        service.description = request.form.get("description")
        service.position = int(request.form.get("position", 0))
        db.session.commit()
        flash("Service updated successfully.")
        return redirect(url_for("services_page"))
    return render_template("admin/edit_service.html", service=service)

@app.post("/project/<string:slug>/comment")
def add_project_comment(slug):
    if not session.get('user_id'):
        flash("Please log in with Google to post a comment.", "error")
        return redirect(url_for('google_login', next=url_for('project', slug=slug)))
    
    project = Project.query.filter_by(slug=slug).first_or_404()
    message = request.form.get("message", "").strip()
    
    if message:
        db.session.add(Comment(
            project_id=project.id,
            user_id=session.get('user_id'),
            message=message
        ))
        db.session.commit()
        flash("Comment posted successfully!", "success")
        
    return redirect(url_for("project", slug=slug))


@app.route("/google/login")
def google_login():
        next_url=request.args.get("next")
        
        if session.get('user_id'):
            flash('Already logged in.', 'success')
            return redirect(next_url)

        if next_url:
            session["google_next"]=next_url

        flow=Flow.from_client_secrets_file(
            GOOGLE_CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=url_for("callback",_external=True)
        )

        auth_url,state=flow.authorization_url(
            prompt="consent",
            access_type="offline",
            include_granted_scopes="true"
        )

        session["google_state"]=state
        session["google_code_verifier"]=flow.code_verifier

        return redirect(auth_url)
  

serializer=URLSafeTimedSerializer(app.secret_key)


@app.route("/reset-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def reset_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = Admin.query.filter_by(email=email).first()

        if user:
            if not user.is_active:
                return render_template(
                    "reset_feedback.html",
                    title="Account Inactive",
                    is_error=True,
                    message="Account inactive. Please contact Admin."
                )

            token = serializer.dumps(user.id, salt="password-reset")
            reset_url = url_for("reset_password_token", token=token, _external=True)

            email_html = f"""
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#f8fafc;padding:30px 0;font-family:'Manrope',Arial,sans-serif;">
                <tr>
                    <td align="center">
                        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="max-width:600px;width:100%;background:#ffffff;border-radius:16px;border:1px solid #d8e2ed;box-shadow:0 10px 30px rgba(7,13,22,0.05);overflow:hidden;">
                            <tr>
                                <td style="padding:36px;">
                                    <h2 style="margin:0 0 16px 0;color:#070d16;font-size:20px;font-weight:800;letter-spacing:-0.02em;">Reset Your Password</h2>
                                    <p style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 24px 0;">
                                        We received a request to reset the password for your OgwenofayaVisuals admin account. Click the button below to choose a new password.
                                    </p>
                                    <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:24px;">
                                        <tr>
                                            <td align="center" style="border-radius:10px;background-color:#368bff;">
                                                <a href="{reset_url}" target="_blank" style="display:inline-block;padding:12px 24px;font-family:'Manrope',Arial,sans-serif;font-size:13px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:10px;background-color:#368bff;box-shadow:0 4px 12px rgba(54,139,255,0.25);">
                                                    Reset Password &rarr;
                                                </a>
                                            </td>
                                        </tr>
                                    </table>
                                    <p style="margin:0;font-size:12px;color:#64748b;border-top:1px solid #e2e8f0;padding-top:16px;line-height:1.5;">
                                        This link expires in 30 minutes. If you did not request a password reset, you can safely ignore this email.
                                    </p>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            </table>
            """

            send_mail(user.id, "Password Reset", email_html)
            return render_template(
                "reset_feedback.html",
                title="Reset Link Sent",
                is_error=False,
                message="Link sent. Please check your email inbox."
            )

        return render_template(
            "reset_feedback.html",
            title="Account Not Found",
            is_error=True,
            message="No account found with that email address."
        )

    return render_template("reset_password.html")

@app.route("/reset-password/<token>",methods=["GET","POST"])
def reset_password_token(token):
    try:
        user_id=serializer.loads(
            token,
            salt="password-reset",
            max_age=1800
        )
    except Exception:
        return "Invalid or expired reset link",400

    user=Admin.query.get_or_404(user_id)

    if request.method=="POST":
        password=request.form.get("password","")

        if len(password)<8:
            return "Password must be at least 8 characters",400

        user.password=generate_password_hash(password)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("reset_password_token.html")
 
@app.route("/google/callback")
def callback():
        if "google_state" not in session or "google_code_verifier" not in session:
            flash("Google login session expired. Please try again.","error")
            return redirect(url_for("index"))

        flow=Flow.from_client_secrets_file(
            GOOGLE_CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            state=session["google_state"],
            redirect_uri=url_for("callback",_external=True)
        )

        flow.code_verifier=session["google_code_verifier"]
        flow.fetch_token(authorization_response=request.url)

        credentials=flow.credentials

        user_info=requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization":f"Bearer {credentials.token}"}
        ).json()

        google_id=user_info["sub"]
        email=user_info["email"].lower()
        name=user_info.get("name") or email.split("@")[0]
        photo=user_info.get("picture")

        user=User.query.filter_by(email=email).first()

        if not user:
            user=User(
                google_id=google_id,
                email=email,
                username=name,
                avatar_url=photo,
                google_method=True,
            )
            db.session.add(user)
        elif not user.is_active:
            flash("Your account has been suspended. Please contact support.","error")
            return redirect(url_for("index"))
        else:
            user.google_id=google_id
            user.username=name
            user.avatar_url=photo
            user.google_method=True

        user.tkv=gen_id("TK",10)
        db.session.commit()

        token=generate_token(user.id,user.tkv)
        session['user_id']=user.id
        session['username']=user.username
        session['photo']=user.avatar_url
        session['user_email']=user.email
        session['token']=token
        
        if user.is_admin:
            session['is_admin']=user.is_admin


        next_url=session.pop("google_next",None)

        session.pop("google_state",None)
        session.pop("google_code_verifier",None)

        flash("Logged in Successfully","success")

        return redirect(next_url)

@app.route("/control/testimonials/edit/<string:id>", methods=["GET", "POST"])
def edit_testimonial(id):
    if not session.get("admin"):
        return redirect(url_for("login"))
    testimonial = Testimonial.query.get_or_404(id)
    if request.method == "POST":
        testimonial.name = request.form.get("name")
        testimonial.company = request.form.get("company")
        testimonial.quote = request.form.get("quote")
        testimonial.position = int(request.form.get("position", 0))
        db.session.commit()
        flash("Testimonial updated successfully.")
        return redirect(url_for("testimonials_page"))
    return render_template("admin/edit_testimonial.html", testimonial=testimonial)


@app.route("/control/users")
@admin_required
def users_page():
    # if not session.get("is_super_admin"):
    #     flash("Super admin privileges required.", "error")
    #     return redirect(url_for("control"))
    
    admins = Admin.query.order_by(Admin.id.desc()).all()
    users = User.query.order_by(User.id.desc()).all()
    
    return render_template(
        "admin/users.html",
        admins=admins,
        users=users
    )

@app.post("/control/admin/toggle/<id>")
@admin_required
def toggle_admin_status(id):
    # if not session.get("is_super_admin"):
    #     return jsonify(ok=False, message="Unauthorized"), 403
    
    admin = Admin.query.get_or_404(id)
    if admin.id == session.get("admin_id"):
        return jsonify(ok=False, message="You cannot modify your own status."), 400

    if admin.is_super_admin:
        return jsonify(ok=False, message="You cannot modify this account."), 400
        
    admin.is_active = not admin.is_active
    db.session.commit()
    
    status_text = "activated" if admin.is_active else "suspended"
    return jsonify(ok=True, message=f"Admin account successfully {status_text}.")

@app.post("/control/user/toggle/<id>")
@admin_required
def toggle_user_status(id):
    # if not session.get("is_super_admin"):
    #     return jsonify(ok=False, message="Unauthorized"), 403
        
    user = User.query.get_or_404(id)
    user.is_active = not user.is_active
    db.session.commit()
    
    status_text = "activated" if user.is_active else "suspended"
    return jsonify(ok=True, message=f"User account successfully {status_text}.")

@app.route("/control/logs")
@admin_required
def logs_page():
    five_days_ago = datetime.utcnow() - timedelta(days=5)
    daily_logs_raw = (
        db.session.query(
            func.date(RequestLog.created_at).label("log_date"),
            func.count(RequestLog.id).label("count")
        )
        .filter(RequestLog.created_at >= five_days_ago, RequestLog.is_deleted == False)
        .group_by(func.date(RequestLog.created_at))
        .all()
    )
    log_counts_map = {str(row.log_date): row.count for row in daily_logs_raw}
    last_5_days = []
    for i in range(4, -1, -1):
        dt = datetime.utcnow() - timedelta(days=i)
        d_str = dt.strftime("%Y-%m-%d")
        if i == 0:
            label = "Today"
        elif i == 1:
            label = "Yesterday"
        else:
            label = dt.strftime("%b %d")
        last_5_days.append({"date_label": label, "count": log_counts_map.get(d_str, 0)})

    frequent_ips_raw = (
        db.session.query(RequestLog.ip_address, func.count(RequestLog.id).label("count"))
        .filter(RequestLog.is_deleted == False)
        .group_by(RequestLog.ip_address)
        .order_by(func.count(RequestLog.id).desc())
        .limit(4)
        .all()
    )
    frequent_ips = [{"ip": row.ip_address, "count": row.count} for row in frequent_ips_raw]

    suspicious_ips_raw = (
        db.session.query(RequestLog.ip_address, func.count(RequestLog.id).label("count"))
        .filter(RequestLog.is_deleted == False, (RequestLog.status_code >= 400) | (RequestLog.path.like("%.php%") | RequestLog.path.like("%wp-%")))
        .group_by(RequestLog.ip_address)
        .order_by(func.count(RequestLog.id).desc())
        .limit(4)
        .all()
    )
    suspicious_ips = [{"ip": row.ip_address, "count": row.count} for row in suspicious_ips_raw]
    
    blocked_ips = BlockedIP.query.all()
    

    top_bots_raw = (
        db.session.query(RequestLog.bot_name, func.count(RequestLog.id).label("count"))
        .filter(RequestLog.is_bot == True, RequestLog.is_deleted == False)
        .group_by(RequestLog.bot_name)
        .order_by(func.count(RequestLog.id).desc())
        .limit(4)
        .all()
    )
    top_bots = [{"name": row.bot_name or "Unknown Bot", "count": row.count} for row in top_bots_raw]

    logs = RequestLog.query.filter_by(is_deleted=False).order_by(RequestLog.created_at.desc()).limit(200).all()
    
    return render_template(
        "admin/logs.html",
        logs=logs,
        last_5_days=last_5_days,
        frequent_ips=frequent_ips,
        suspicious_ips=suspicious_ips,
        top_bots=top_bots,
        blocked_ips=blocked_ips
    )
    
    
@app.post("/control/logs/bulk-delete")
@admin_required
def bulk_delete_logs():
    log_ids = request.form.getlist("log_ids")
    if log_ids:
        RequestLog.query.filter(RequestLog.id.in_(log_ids)).delete(synchronize_session=False)
        db.session.commit()
        flash(f"{len(log_ids)} log entries permanently deleted.")
    return redirect(url_for("logs_page"))



@app.errorhandler(401)
def unauthorized_error(error):
    return render_template("errors/401.html"), 401

@app.errorhandler(404)
def not_found_error(error):
    return render_template("errors/404.html"), 404

@app.errorhandler(429)
def ratelimit_error(error):
    return render_template("errors/429.html"), 429

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback() 
    return render_template("errors/500.html"), 500

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    checkProcess()
    app.run(debug=True)