from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)

app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clarity.db'
db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(db.Model, UserMixin):
                id = db.Column(db.Integer, primary_key=True)
                username = db.Column(db.String(80), unique=True, nullable=False)
                email = db.Column(db.String(120), unique=True, nullable=False)
                password = db.Column(db.String(200), nullable=False)
                entries = db.relationship('Entry', backref='owner', lazy=True)

class Entry(db.Model):
                id = db.Column(db.Integer, primary_key=True)
                content = db.Column(db.Text, nullable=False)
                mode = db.Column(db.String(10), default="Personal")
                ai = db.Column(db.Text, nullable=True)
                mood = db.Column(db.Integer, nullable=True)
                created_at = db.Column(db.DateTime, default=datetime.utcnow)
                user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
        
                