import os

from flask import Flask


def create_app(test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__)
    app.config.from_object('scheduler.config.Config')

    # register the database commands
    from scheduler import db

    db.init_app(app)

    # apply the blueprints to the app
    from scheduler import auth, scheduler

    app.register_blueprint(auth.bp)
    app.register_blueprint(scheduler.bp)

    app.add_url_rule("/", endpoint="index")

    return app
