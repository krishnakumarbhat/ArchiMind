"""Production entrypoint (directive layout).

Delegates to the deploy-compatible Flask factory in app.py so existing
Docker/gunicorn/scripts entrypoints keep working unchanged.
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("FLASK_PORT", "5000")))
