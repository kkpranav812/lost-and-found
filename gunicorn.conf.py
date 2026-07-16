import os
import multiprocessing

# Gunicorn configuration file for Flask-SocketIO
# https://docs.gunicorn.org/en/stable/settings.html

# Bind to PORT environment variable, defaults to 5000
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"

# We must use eventlet or gevent for Flask-SocketIO to work properly in production
worker_class = "eventlet"

# Socket.IO recommends 1 worker if you are not using a message queue (like Redis or RabbitMQ)
# Since we haven't configured a message queue for SocketIO, we'll stick to 1 worker.
# If we scale up workers, we MUST add a message queue for cross-process WebSocket events.
workers = 1

# Thread count
threads = 10

# Timeout (longer timeout for WebSocket persistence)
timeout = 120
keepalive = 65

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
