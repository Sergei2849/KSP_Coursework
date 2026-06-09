import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, send_from_directory
from flask.json.provider import DefaultJSONProvider

from backend.log import get_logger
from backend.routes.api import api_bp
from backend.routes.auth import auth_bp

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = BASE_DIR / "public"
load_dotenv(BASE_DIR / ".env")


class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def create_app():
    get_logger()
    app = Flask(__name__)
    app.json = CustomJSONProvider(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)

    @app.get("/")
    def index():
        return send_from_directory(PUBLIC_DIR, "index.html")

    @app.route("/<path:path>")
    def static_files(path):
        target = PUBLIC_DIR / path
        if target.is_file():
            return send_from_directory(PUBLIC_DIR, path)
        abort(404)

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG") == "1")
