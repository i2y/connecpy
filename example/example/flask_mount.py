from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from .haberdasher_connecpy import HaberdasherWSGIApplication
from .wsgi_service import HaberdasherService

haberdasher_app = HaberdasherWSGIApplication(HaberdasherService())

app = Flask(__name__)


@app.route("/healthz")
def health() -> str:
    return "OK"


app.wsgi_app = DispatcherMiddleware(
    app.wsgi_app, {haberdasher_app.path: haberdasher_app}
)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=3000, debug=True)
