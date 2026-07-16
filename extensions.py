from flask_socketio import SocketIO

# Instantiate SocketIO without an app.
# We will initialize it in app.py with socketio.init_app(app).
socketio = SocketIO(cors_allowed_origins="*")
