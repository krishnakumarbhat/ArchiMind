"""ArchiMind production entrypoint and WSGI factory target.

Run locally with ``python3 main.py`` or serve with
``gunicorn 'main:app'`` (see Dockerfile).
"""
import os

from src.web._00_application import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("FLASK_PORT", "5000")))
