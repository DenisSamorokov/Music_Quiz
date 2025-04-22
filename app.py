from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import random
from datetime import datetime
import re
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')

if os.getenv('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL').replace("postgres://", "postgresql://")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///music_quiz.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)

DEEZER_API_URL = "https://api.deezer.com"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    score = db.Column(db.Integer, default=0)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


with app.app_context():
    db.create_all()
    if not Message.query.first():
        welcome_message = Message(
            username='Система',
            message='Добро пожаловать в чат Music Quiz!',
            timestamp=datetime.utcnow()
        )
        db.session.add(welcome_message)
        db.session.commit()

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def detect_language_from_title(title, artist_name):
    print(f"Detecting language for title: {title}, artist: {artist_name}")
    title = title.lower()
    artist_name = artist_name.lower()

    if re.search(r'[\u0400-\u04FF]', title) or re.search(r'[\u0400-\u04FF]', artist_name):
        print(f"Detected language: ru (Cyrillic characters)")
        return 'ru'

    if re.search(r'[\u00C0-\u00FF]', title) or re.search(r'[\u00C0-\u00FF]', artist_name):
        if re.search(r'[ñáéíóú]', title) or re.search(r'[ñáéíóú]', artist_name):
            print(f"Detected language: es (Spanish characters)")
            return 'es'
        if re.search(r'[éèêëç]', title) or re.search(r'[éèêëç]', artist_name):
            print(f"Detected language: fr (French characters)")
            return 'fr'
        if re.search(r'[äöüß]', title) or re.search(r'[äöüß]', artist_name):
            print(f"Detected language: de (German characters)")
            return 'de'

    if re.search(r'^[\x00-\x7F]*$', title) and re.search(r'^[\x00-\x7F]*$', artist_name):
        print(f"Detected language: en (Basic Latin characters)")
        return 'en'

    print(f"Language defaulted to: en for title: {title}, artist: {artist_name}")
    return 'en'


def fetch_tracks(difficulty, language='any', style='any'):
    min_rank = {
        'easy': 150000,
        'medium': 100000,
        'hard': 70000
    }.get(difficulty, 100000)

    # Используем глобальный чарт
    url = f"{DEEZER_API_URL}/chart/0/tracks"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Error fetching tracks: {response.status_code}")
        return []

    tracks = response.json().get('data', [])

    # Фильтрация
    tracks = [
        track for track in tracks
        if track.get('preview') and
           track.get('rank', 0) >= min_rank and
           track.get('duration', 0) >= 30 and
           not track.get('explicit_lyrics', True)
    ]

    # Языковая фильтрация
    filtered_tracks = []
    for track in tracks:
        title = track['title']
        artist = track['artist']['name']
        track_language = detect_language_from_title(title, artist)
        if language == 'any' or track_language == language:
            filtered_tracks.append(track)

    random.shuffle(filtered_tracks)
    return filtered_tracks[:20]


def select_track_and_options(tracks):
    if not tracks:
        return None, []
    correct_track = random.choice(tracks)
    correct_artist = correct_track['artist']['name']
    options = []
    used_artists = {correct_artist}
    available_tracks = [track for track in tracks if track['artist']['name'] not in used_artists]

    while len(options) < 3 and available_tracks:
        track = random.choice(available_tracks)
        artist = track['artist']['name']
        if artist not in used_artists:
            options.append({
                'id': track['id'],
                'title': track['title'],
                'artist': artist,
                'preview_url': track['preview']
            })
            used_artists.add(artist)
        available_tracks = [t for t in available_tracks if t['artist']['name'] not in used_artists]

    if len(options) < 3:
        return None, []

    options.append({
        'id': correct_track['id'],
        'title': correct_track['title'],
        'artist': correct_artist,
        'preview_url': correct_track['preview']
    })

    random.shuffle(options)

    formatted_correct_track = {
        'id': correct_track['id'],
        'title': correct_track['title'],
        'artist': correct_artist,
        'preview_url': correct_track['preview']
    }

    return formatted_correct_track, options

@app.route('/')
def index():
    leaders = User.query.order_by(User.score.desc()).limit(5).all()
    messages = Message.query.order_by(Message.timestamp.desc()).limit(3).all()
    return render_template('index.html', leaders=leaders, messages=messages)

@app.route('/play/<difficulty>', methods=['GET', 'POST'])
@login_required
def play(difficulty):
    language = request.args.get('language', 'any')
    style = request.args.get('style', 'any')
    tracks = fetch_tracks(difficulty, language=language, style=style)
    track, options = select_track_and_options(tracks)
    if not track or len(options) < 4:
        flash("Не удалось найти достаточно треков с разными исполнителями. Попробуйте другой фильтр.", "error")
        return redirect(url_for('index'))
    duration = {'easy': 30, 'medium': 20, 'hard': 10}.get(difficulty, 30)
    if request.method == 'POST':
        guess = request.form.get('guess')
        track_id = request.form.get('track_id')
        track_title = request.form.get('track_title')
        track_artist = request.form.get('track_artist')
        correct = str(guess) == str(track_id)
        if correct:
            points = {'easy': 5, 'medium': 10, 'hard': 15}.get(difficulty, 5)
            current_user.score += points
            db.session.commit()
        return render_template('result.html', correct=correct, track={'title': track_title, 'artist': track_artist},
                               difficulty=difficulty, language=language, style=style)
    leaders = User.query.order_by(User.score.desc()).limit(5).all()
    messages = Message.query.order_by(Message.timestamp.desc()).limit(3).all()
    return render_template('play.html', track=track, options=options, difficulty=difficulty, duration=duration,
                           leaders=leaders, messages=messages, language=language, style=style)
@app.route('/leaderboard')
def leaderboard():
    leaders = User.query.order_by(User.score.desc()).limit(10).all()
    messages = Message.query.order_by(Message.timestamp.desc()).limit(3).all()
    return render_template('leaderboard.html', leaders=leaders, messages=messages)


@app.route('/chat')
@login_required
def chat():
    leaders = User.query.order_by(User.score.desc()).limit(5).all()
    messages = Message.query.order_by(Message.timestamp.desc()).all()
    return render_template('chat.html', messages=messages, leaders=leaders)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'error')
    leaders = User.query.order_by(User.score.desc()).limit(5).all()
    messages = Message.query.order_by(Message.timestamp.desc()).limit(3).all()
    return render_template('login.html', leaders=leaders, messages=messages)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Имя пользователя уже занято', 'error')
        else:
            user = User(username=username, password=generate_password_hash(password), score=0)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('index'))
    leaders = User.query.order_by(User.score.desc()).limit(5).all()
    messages = Message.query.order_by(Message.timestamp.desc()).limit(3).all()
    return render_template('register.html', leaders=leaders, messages=messages)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@socketio.on('message')
def handle_message(data):
    message = Message(
        username=current_user.username,
        message=data['message'],
        timestamp=datetime.utcnow()
    )
    db.session.add(message)
    db.session.commit()
    emit('message', {
        'username': message.username,
        'message': message.message,
        'timestamp': message.timestamp.isoformat()
    }, broadcast=True)


if __name__ == '__main__':
    socketio.run(app, debug=True)