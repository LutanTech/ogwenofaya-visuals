from datetime import datetime, timedelta
from functools import wraps
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import string
import subprocess
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
import requests
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from known_bots import detect_bot
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change_this_secret")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///ogwenofaya.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["2000 per day", "500 per hour"]
)

IMAGE_DIR = os.path.join(app.root_path, "static", "resources", "images")
VIDEO_DIR = os.path.join(app.root_path, "static", "resources", "videos")
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

def get_location_by_ip(ip):
    if not ip or ip in ('127.0.0.1', '::1', 'localhost'):
        return "Localhost"
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,country,city"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=1.5) as response:
            data = json.loads(response.read().decode())
            if data.get('status') == 'success':
                city = data.get('city', '')
                country = data.get('country', '')
                return f"{city}, {country}".strip(', ')
    except Exception:
        pass
    return "Unknown"

class Project(db.Model):
    id = db.Column(db.String(30), primary_key=True, default=lambda: gen_id("PRJ_"))
    title = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(255))
    video = db.Column(db.String(255))
    featured = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta))
    images = db.relationship(
        "ProjectImage",
        backref="project",
        cascade="all, delete-orphan",
        order_by="ProjectImage.id"
    )

class ProjectImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(30), db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta))
    
    
class ProjectVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(30), db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta))
    

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(100), nullable=False)
    avatar_url = db.Column(db.String(255), nullable=True)
    google_method = db.Column(db.Boolean, default=False)
    email_method = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False, nullable=False)
    tkv = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta))
    password = db.Column(db.String(255), nullable=True)
    


Project.videos = db.relationship(
    "ProjectVideo",
    backref="project",
    cascade="all, delete-orphan",
    order_by="ProjectVideo.id"
)

Project.comments = db.relationship(
    "Comment",
    backref="project",
    cascade="all, delete-orphan",
    order_by="Comment.id.desc()"
)

class Service(db.Model):
    id = db.Column(db.String(30), primary_key=True, default=lambda: gen_id("SRV_"))
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(255))
    position = db.Column(db.Integer, default=0)
    is_deleted = db.Column(db.Boolean, default=False)
    
    
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(30), db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta))

    author = db.relationship("User", backref=db.backref("comments", cascade="all, delete-orphan"))
    


class Testimonial(db.Model):
    id = db.Column(db.String(30), primary_key=True, default=lambda: gen_id("TST_"))
    name = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(150))
    quote = db.Column(db.Text, nullable=False)
    position = db.Column(db.Integer, default=0)
    is_deleted = db.Column(db.Boolean, default=False)

class Inquiry(db.Model):
    id = db.Column(db.String(30), primary_key=True, default=lambda: gen_id("INQ_"))
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), nullable=False)
    phone = db.Column(db.String(50))
    service = db.Column(db.String(120))
    message = db.Column(db.Text, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta))

class Admin(db.Model):
    id = db.Column(db.String(30), primary_key=True, default=lambda: gen_id("ADM_"))
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta))

class RequestLog(db.Model):
    id = db.Column(db.String(30), primary_key=True, default=lambda: gen_id("LOG_"))
    method = db.Column(db.String(10), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    status_code = db.Column(db.Integer, nullable=False)
    ip_address = db.Column(db.String(50))
    location = db.Column(db.String(120))
    user_agent = db.Column(db.String(255))
    is_bot = db.Column(db.Boolean, default=False)
    bot_name = db.Column(db.String(100), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow() + timedelta(hours=delta))

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

@app.context_processor
def globals():
    return {
        "site_name": "OgwenofayaVisuals",
        "year": datetime.utcnow().year
    }

@app.after_request
def log_request(response):
    if request.path.startswith('/static/') or request.path.startswith('/video/') or request.path == '/favicon.ico':
        return response
    try:
        ua = request.user_agent.string if request.user_agent else ""
        is_bot, bot_name = detect_bot(ua)
        ip = request.remote_addr
        location = get_location_by_ip(ip)
        log_entry = RequestLog(
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            ip_address=ip,
            location=location,
            user_agent=ua[:255],
            is_bot=is_bot,
            bot_name=bot_name
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Logging error: {e}", flush=True)
    return response

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
@limiter.limit("5 per minute")
def register():
    if Admin.query.first():
        return redirect(url_for("login"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if not username or not password:
            flash("Username and password are required.")
            return render_template("register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.")
            return render_template("register.html")
        admin = Admin(
            username=username,
            password=generate_password_hash(password)
        )
        db.session.add(admin)
        db.session.commit()
        flash("Admin account created. You can now login.")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password, password):
            session["admin"] = True
            session["admin_id"] = admin.id
            return redirect(url_for("control"))
        flash("Invalid username or password.")
    return render_template("login.html")

@app.get("/logout")
def logout():
    session.pop("admin", None)
    session.pop("admin_id", None)
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

@app.post("/control/project")
@admin_required
def add_project():
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    if not title or not category:
        return admin_form_response("Title and category are required.", False, 400)
    slug = unique_slug(title)
    image_files = request.files.getlist("images")
    if not any(file and file.filename for file in image_files):
        legacy_image = request.files.get("image")
        image_files = [legacy_image] if legacy_image and legacy_image.filename else []
    saved_images = []
    for image_file in image_files:
        filename = save_image_upload(image_file)
        if filename:
            saved_images.append(filename)
    
    video_files = request.files.getlist("videos")
    if not any(file and file.filename for file in video_files):
        legacy_video = request.files.get("video")
        video_files = [legacy_video] if legacy_video and legacy_video.filename else []
    saved_videos = []
    for video_file in video_files:
        filename = save_upload(video_file, VIDEO_DIR, "VID_")
        if filename:
            saved_videos.append(filename)

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
    db.session.commit()
    return admin_form_response("Project created.", True, 201)

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
    if start > 0:
        command += ["-ss", f"{start:.3f}"]
    command += [
        "-i", path,
        "-map", "0:v:0",
        "-map", "0:a?",
        "-vf", f"scale=-2:min({quality}\\,ih)",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "frag_keyframe+empty_moov+default_base_moof",
        "-f", "mp4",
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
        
        image_files = request.files.getlist("images")
        saved_images = []
        for image_file in image_files:
            filename = save_image_upload(image_file)
            if filename:
                saved_images.append(filename)
        if saved_images:
            if not project.image:
                project.image = saved_images[0]
            for filename in saved_images:
                db.session.add(ProjectImage(project_id=project.id, filename=filename))

        video_files = request.files.getlist("videos")
        saved_videos = []
        for video_file in video_files:
            filename = save_upload(video_file, VIDEO_DIR, "VID_")
            if filename:
                saved_videos.append(filename)
        if saved_videos:
            if not project.video:
                project.video = saved_videos[0]
            for filename in saved_videos:
                db.session.add(ProjectVideo(project_id=project.id, filename=filename))

        db.session.commit()
        flash("Project updated successfully.")
        return redirect(url_for("projects_page"))
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
    
@app.route("/google/callback")
def callback():
        if "google_state" not in session or "google_code_verifier" not in session:
            flash("Google login session expired. Please try again.","error")
            return redirect(url_for("home"))

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
            return redirect(url_for("home"))
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
        top_bots=top_bots
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