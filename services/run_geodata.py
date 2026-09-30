from http.server import ThreadingHTTPServer
from geodata import GeoHandler

# Recover queued and interrupted imports only after durable state has been
# hydrated; importing geodata as a module must not start background jobs.
GeoHandler.store.hydrate()
GeoHandler.recover_import_runs()
ThreadingHTTPServer(("0.0.0.0", 8003), GeoHandler).serve_forever()
