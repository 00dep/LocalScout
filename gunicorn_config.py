import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 50
preload_app = True

accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"
proc_name = "localscout"
