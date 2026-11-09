from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import secrets
import string

delta = 3

def gen_id(prefix, len=8):
    chars = string.digits + string.ascii_letters
    return prefix + "".join(secrets.choice(chars) for _ in range(len))

db = SQLAlchemy()

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
    created_at = db.Column(db.DateTime, default=lambda:datetime.utcnow() + timedelta(hours=delta))
    images = db.relationship(
        "ProjectImage",
        backref="project",
        cascade="all, delete-orphan",
        order_by="ProjectImage.id"
    )
    
    files = db.relationship('ProjectFile', backref='project', cascade='all, delete-orphan')

class ProjectImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(30), db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda:datetime.utcnow() + timedelta(hours=delta))
    
    
class ProjectVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(30), db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda:datetime.utcnow() + timedelta(hours=delta))
    

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
    created_at = db.Column(db.DateTime, default=lambda:datetime.utcnow() + timedelta(hours=delta))
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
    created_at = db.Column(db.DateTime, default=lambda:datetime.utcnow() + timedelta(hours=delta))

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
    created_at = db.Column(db.DateTime, default=lambda:datetime.utcnow() + timedelta(hours=delta))

class Admin(db.Model):
    id = db.Column(db.String(30), primary_key=True, default=lambda: gen_id("ADM_"))
    google_id = db.Column(db.String(100), unique=True, nullable=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(180), nullable=True, unique=True)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda:datetime.utcnow() + timedelta(hours=delta))
    google_method = db.Column(db.Boolean, default=False)
    email_method = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False, nullable=False)
    tkv = db.Column(db.String(50), nullable=True)

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
    created_at = db.Column(db.DateTime, default=lambda:datetime.utcnow() + timedelta(hours=delta))
    is_verified_bot = db.Column(db.Boolean, default=False, nullable=False)
    bot_hostname = db.Column(db.String(255))
    
    
class BlockedIP(db.Model):
    id = db.Column(db.String(30), primary_key=True, default=lambda: gen_id("BL_"))
    ip_address = db.Column(db.String(50), unique=True, nullable=False, index=True)
    blocked_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=delta))
    
    
class Registration(db.Model):
    id = db.Column(db.String(30), primary_key=True, default=lambda: gen_id("REG_"))
    status = db.Column(db.Boolean, default=False)
    
class ProjectFile(db.Model):
    __tablename__ = 'project_files'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(30), db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.utcnow() + timedelta(hours=delta))