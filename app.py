from flask import Flask
from flask_socketio import SocketIO
from flask_login import LoginManager
import os
from models.models import db, User, init_db
from routes.routes import init_routes

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SESSION_TYPE'] = 'filesystem'

if os.getenv('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL').replace("postgres://", "postgresql://")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///music_quiz.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация базы данных
db.init_app(app)
init_db(app)

socketio = SocketIO(app)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'routes.login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Инициализируем маршруты
init_routes(app, socketio)

if __name__ == '__main__':
    socketio.run(app, debug=True)