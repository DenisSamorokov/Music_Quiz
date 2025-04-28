from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, login_required, logout_user, current_user
from flask_socketio import emit
from models.models import User, Message, db
from utils.track_utils import select_track_and_options
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

def init_routes(app: Flask, socketio=None):
    @app.route('/')
    def index():
        leaders = User.query.order_by(User.score.desc()).limit(5).all()
        messages = Message.query.order_by(Message.timestamp.desc()).limit(3).all()
        genres = ["any", "Pop", "Rock", "Hip-Hop/Rap", "Electronic", "Jazz", "Classical"]
        return render_template('index.html', leaders=leaders, messages=messages, genres=genres)

    @app.route('/play/<difficulty>', methods=['GET', 'POST'])
    @login_required
    def play(difficulty):
        style = request.args.get('style', 'any')
        language = request.args.get('language', 'ru')
        country = request.args.get('country', None)

        if 'used_track_ids' not in session:
            session['used_track_ids'] = []
        if 'used_artists' not in session or not isinstance(session['used_artists'], dict):
            session['used_artists'] = {'easy': [], 'medium': [], 'hard': []}

        track, options = select_track_and_options(difficulty, style=style, country=country)
        if not track or len(options) < 4:
            print(f"[{difficulty.upper()}] Не удалось выбрать трек или варианты ответа")
            flash("Не удалось найти достаточно треков. Попробуйте другой уровень сложности или жанр.", "error")
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
            return jsonify({
                'correct': correct,
                'track': {'title': track_title, 'artist': track_artist}
            })

        track_for_template = {
            'id': track['id'],
            'title': track['title'],
            'artist': track['artist']['name'],
            'preview_url': track['preview']
        }
        options_for_template = [
            {
                'id': opt['id'],
                'title': opt['title'],
                'artist': opt['artist']['name'],
                'preview_url': opt.get('preview', None)
            }
            for opt in options
        ]

        print(f"Preview URL для трека: {track_for_template['preview_url']}")

        return render_template('play.html', track=track_for_template, options=options_for_template,
                               difficulty=difficulty, duration=duration, style=style, language=language)

    @app.route('/reset-session', methods=['POST'])
    @login_required
    def reset_session():
        session.clear()
        session['used_track_ids'] = []
        session['used_artists'] = {'easy': [], 'medium': [], 'hard': []}
        session['last_artist_index'] = {'easy': 0, 'medium': 0, 'hard': 0}
        flash("История использованных треков сброшена.", "success")
        return redirect(url_for('index'))

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
                flash('Неверное имя пользователя или пароль.', 'error')
        return render_template('login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            if User.query.filter_by(username=username).first():
                flash('Имя пользователя уже занято.', 'error')
            else:
                user = User(username=username, password=generate_password_hash(password))
                db.session.add(user)
                db.session.commit()
                flash('Регистрация успешна! Войдите в систему.', 'success')
                return redirect(url_for('login'))
        return render_template('register.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('index'))

    @socketio.on('connect')
    def handle_connect():
        messages = Message.query.order_by(Message.timestamp.desc()).all()
        for message in messages:
            emit('chat_message', {
                'username': message.username,
                'message': message.message,
                'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            })

    @socketio.on('send_message')
    def handle_message(data):
        message = Message(
            username=current_user.username,
            message=data['message'],
            timestamp=datetime.utcnow()
        )
        db.session.add(message)
        db.session.commit()
        emit('chat_message', {
            'username': message.username,
            'message': message.message,
            'timestamp': message.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }, broadcast=True)