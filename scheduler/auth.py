import functools

from flask import Blueprint
from flask import current_app
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash

from scheduler.db import get_db

bp = Blueprint("auth", __name__, url_prefix="/auth")


def login_required(view):
    """View decorator that redirects anonymous users to the login page."""

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not g.user:
            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view


@bp.before_app_request
def load_logged_in_user():
    """If a user id is stored in the session, load the user object from
    the database into ``g.user``."""
    user_id = session.get("user_id")

    if not user_id:
        g.user = None
    else:
        cur = get_db().cursor()
        cur.execute("SELECT * FROM Users WHERE id = %s", (user_id,))
        g.user = cur.fetchone()


@bp.route("/register", methods=("GET", "POST"))
def register():
    """Register a new user.

    Validates that the username is not already taken. Hashes the
    password for security.
    """
    if request.method == "POST":
        email = request.form["email"]
        name = request.form["name"]
        password = request.form["password"]
        db = get_db()
        cur = db.cursor()
        error = None

        if not email:
            error = "Email is required."
        elif not name:
            error = "Name is required."
        elif not password:
            error = "Password is required."

        if not error:
            try:
                cur.execute(
                    "INSERT INTO Users (email, name, password) VALUES (%s, %s, %s)",
                    (email, name, generate_password_hash(password)),
                )
                db.commit()
            except db.IntegrityError as e:
                # The email was already used, which caused the
                # commit to fail. Show a validation error.
                error = f"User account using {email} is already registered"
                if current_app.config["DEBUG"]:
                    error += f": ({e})"
            else:
                # Success, go to the login page.
                return redirect(url_for("scheduler.index"))

        flash(error)

    return render_template("auth/register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
    """Log in a registered user by adding the user id to the session."""
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        db = get_db()
        cur = db.cursor()
        error = None
        cur.execute("SELECT * FROM Users WHERE email = %s", (email,))
        user = cur.fetchone()

        if not user or not check_password_hash(user["password"], password):
            error = "Login failed."

        if not error:
            # store the user id in a new session and return to the index
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("index"))

        flash(error)

    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    """Clear the current session, including the stored user id."""
    session.clear()
    return redirect(url_for("index"))
