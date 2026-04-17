from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from groq import Groq

app = Flask(__name__)

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'clarity-dev-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clarity.db'
db = SQLAlchemy(app)
with app.app_context():
    db.create_all()

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
                tags = db.Column(db.Text, nullable=True , default="")
                mode = db.Column(db.String(10), default="Personal")
                ai = db.Column(db.Text, nullable=True)
                mood = db.Column(db.Integer, nullable=True)
                created_at = db.Column(db.DateTime, default=datetime.utcnow)
                user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Message(db.Model):
                id = db.Column(db.Integer, primary_key=True)
                role = db.Column(db.String(10), nullable=False)
                content = db.Column(db.Text, nullable=False)
                entry_id = db.Column(db.Integer, db.ForeignKey('entry.id'), nullable=False) 
                created_at = db.Column(db.DateTime, default=datetime.utcnow)  

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
        if request.method == 'POST':
            email = request.form.get('email')
            username = request.form.get('username')
            password = request.form.get('password')
            existing_user = User.query.filter_by(username=username).first()
            existing_email = User.query.filter_by(email=email).first()
            if existing_user or existing_email:
                flash('Username or email already taken')
                return redirect(url_for('register'))
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, email=email, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
        return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for('dashboard'))
            flash('Invalid username or password')
        return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    entries = Entry.query.filter_by(user_id=current_user.id).order_by(Entry.created_at.desc()).first()
    return render_template('dashboard.html', latest_entry=entries)

@app.route('/new_entry', methods=['GET', 'POST'])
@login_required
def new_entry():
       if request.method == 'POST':
            content = request.form.get('content')
            tags = request.form.get('tags')
            mode = request.form.get('mode')
            mood = request.form.get('mood')
            groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            chat = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": f"You are Clarity, a warm and supportive AI journaling companion. The user wrote this journal entry (mode: {mode}, mood: {mood}/10): \"{content}\". Respond with a short, empathetic, thoughtful reflection in 2-3 sentences."}])
            ai_response = chat.choices[0].message.content
            new_entry = Entry(content=content, tags=tags, mode=mode, mood=mood, ai=ai_response, user_id=current_user.id)
            db.session.add(new_entry)
            db.session.commit()
            return redirect(url_for('entry', id=new_entry.id))
       return render_template('new_entry.html')

@app.route('/entry/<int:id>')
@login_required
def entry(id):
       entry = Entry.query.get_or_404(id)
       user_id = entry.user_id
       if user_id == current_user.id:
              messages = Message.query.filter_by(entry_id=id).order_by(Message.created_at).all()
              return render_template('entry.html', entry=entry, messages=messages)
       else:
              flash('You do not have permission to view this entry')
              return redirect(url_for('dashboard'))
       
@app.route('/entry/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_entry(id):
        entry = Entry.query.get_or_404(id)
        if entry.user_id != current_user.id:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            entry.content = request.form.get('content')
            entry.mode = request.form.get('mode')
            entry.mood = request.form.get('mood')
            db.session.commit()
            return redirect(url_for('entry', id=entry.id))
        return render_template('edit_entry.html', entry=entry)

@app.route('/entry/<int:id>/delete', methods=['POST'])
@login_required
def delete_entry(id):
        entry = Entry.query.get_or_404(id)
        if entry.user_id != current_user.id:
            return redirect(url_for('dashboard'))
        db.session.delete(entry)
        db.session.commit()
        return redirect(url_for('entries'))

@app.route('/entries')
@login_required
def entries():
       entries = Entry.query.filter_by(user_id=current_user.id).all()
       return render_template('entries.html', entries=entries)

@app.route('/search', methods=['GET'])
@login_required
def search():
       q = request.args.get('q')
       entries = Entry.query.filter_by(user_id=current_user.id).filter(Entry.tags.contains(q)).all()
       return render_template('search.html', entries=entries, q=q)

@app.route('/entry/<int:id>/chat', methods=['POST'])
@login_required
def entry_chat(id):
        entry = Entry.query.get_or_404(id)
        if entry.user_id != current_user.id:
            return redirect(url_for('dashboard'))

        user_message = request.form.get('message')

        # Load previous messages for this entry
        history = Message.query.filter_by(entry_id=id).order_by(Message.created_at).all()

        # Build conversation for Groq
        messages = [{"role": "system", "content": f"You are Clarity, a warm journaling companion that talks through and provides insight also please keep the response short,bewteen 2-3 sentences but long enough for diaglogues. The user's original entry was: '{entry.content}'"}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_message})

        # Get Groq response
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        chat = groq_client.chat.completions.create(model="llama-3.1-8b-instant", messages=messages)
        ai_reply = chat.choices[0].message.content

        # Save both messages to DB
        db.session.add(Message(role="user", content=user_message, entry_id=id))
        db.session.add(Message(role="assistant", content=ai_reply, entry_id=id))
        db.session.commit()

        return redirect(url_for('entry', id=id))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)


       
        