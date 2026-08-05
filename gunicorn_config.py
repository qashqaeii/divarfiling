"""
Gunicorn configuration file for Django production server
"""
import multiprocessing
import os

# Server socket
bind = "127.0.0.1:8000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 600  # بک‌آپ دیتابیس و آپلودهای سنگین (پیش‌فرض ۳۰s برای export کافی نیست)
keepalive = 2

# Logging
accesslog = os.path.join(os.path.dirname(__file__), "logs", "gunicorn_access.log")
errorlog = os.path.join(os.path.dirname(__file__), "logs", "gunicorn_error.log")
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "divar_shop"

# Server mechanics
daemon = False
pidfile = os.path.join(os.path.dirname(__file__), "gunicorn.pid")
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (اگر از SSL استفاده می‌کنید، این خطوط را فعال کنید)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

