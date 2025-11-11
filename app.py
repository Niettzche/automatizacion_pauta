"""Aplicación Flask para automatización de leads."""
from flask import Flask, jsonify
from dotenv import load_dotenv

# Carga variables de entorno antes de importar el resto de módulos
load_dotenv()

from routes.leads import leads_bp  # noqa: E402


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(leads_bp, url_prefix="/api")

    @app.route("/health", methods=["GET"])
    def health_check():
        return jsonify({"ok": True})

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
