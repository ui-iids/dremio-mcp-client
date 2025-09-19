from flask import Flask, render_template, send_file
from tomllib import load as tomlload
from werkzeug import exceptions
from collections import namedtuple

# Only needed if serving Pages
from .pages import pages
from flask_bootstrap import Bootstrap5 as Bootstrap

# Only needed if serving APIs
from .api import register_apis

# Only needed if using a database.
# For instructions on other databases or plugins,
# including necessary packages, see `database.py`.
from .database import register_database


def create_app(config_filename="config.toml", config_override={}):
    app = Flask(__name__)

    # Register Database
    # * Remove if not using database.
    register_database(app)

    # Register Rendered Pages Blueprint
    # * Remove if not serving pages.
    Bootstrap(app)
    app.register_blueprint(pages)

    # Error Handlers
    # Customize to the richness/communication/sensitivity needed for the project at hand.
    @app.errorhandler(exceptions.NotFound)
    def page_not_found(e):
        return render_template("pages/404.html"), 404

    @app.errorhandler(exceptions.InternalServerError)
    def server_error(e):
        return render_template("pages/error.html"), 500

    # Accepts config from:
    # * A file at `project_name/config.toml` or a name specified in `config_filename`
    # * A Python dictionary or dictionary-like passed as `config_override`
    # * argument, or a file specified by environment variable `APP_CONFIG_FILE`
    #
    # Some relevant configuration is set downstream in the individual blueprints or modules,
    # Such as Database Connection URIs or API metadata.
    app.config.from_file(config_filename, load=tomlload, text=False, silent=True)
    app.config.from_object(namedtuple("Config", config_override)(**config_override))
    app.config.from_envvar("APP_CONFIG_FILE", silent=True)

    # For debug purposes, we compile CSS every time it changes.
    # For deployments, ensure the `static.css` is up to date.
    if app.debug:
        from sassutils.wsgi import SassMiddleware

        app.wsgi_app = SassMiddleware(
            app.wsgi_app,
            {
                "project_name": {
                    "sass_path": "static/sass",
                    "css_path": "static/css",
                    "wsgi_path": "/static/css",
                    "strip_extension": True,
                }
            },
        )

    # Register the APIs paths from `project_name/api`.
    # Remove if API is not needed.
    register_apis(app)

    # Serve a basic PWA application with a static `offline` page.
    # Extend the service worker for more advanced cached functionality.
    if app.config.get("SERVE_PWA"):

        @app.route("/manifest.json", methods=["GET"])
        def route_app_manifest():
            return send_file(
                "static/manifest.json", mimetype="application/manifest+json"
            )

        @app.route("/sw.js", methods=["GET"])
        def route_sw_root():
            return send_file("static/js/sw.js", mimetype="application/javascript")

    return app
