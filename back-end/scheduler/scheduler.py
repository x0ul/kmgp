from datetime import datetime

from flask import Blueprint
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from werkzeug.exceptions import abort

from scheduler.auth import login_required
from scheduler.db import get_db

bp = Blueprint("scheduler", __name__)


@bp.route("/")
def index():
    """Show all the episodes, most recent first."""
    db = get_db()
    # TODO do the join thing
    episodes = db.execute(
        "SELECT e.id, show_id, title, air_date, url, description, created_by, updated_by, created_at, updated_at"
        " FROM Episodes e"
        " ORDER BY air_date DESC"
    ).fetchall()
    return render_template("scheduler/index.html", episodes=episodes)


def get_episode(id):
    """Get an episode by id.

    TODO use the join table to check if the current auth'd user is an owner.

    :param id: id of episode to get
    TODO :param check_user: require the current user to be an owner
    :return: the episode
    :raise 404: if an episode with the given id doesn't exist
    :raise 403: if the current user isn't an owner
    """
    post = (
        get_db()
        .execute(
            "SELECT e.id, show_id, air_date, url, created_at, updated_at, description, title"
            " FROM Episodes e"
            " WHERE e.id = ?",
            (id,),
        )
        .fetchone()
    )

    if post is None:
        abort(404, f"Post id {id} doesn't exist.")

    if check_author and post["author_id"] != g.user["id"]:
        abort(403)

    return post


@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    """Create a new post for the current user."""
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        air_date = request.form["air_date"]
        audio_file = request.form["audio_file"]
        error = None

        # TODO server-side validation of fields

        air_date = datetime.strptime(air_date, "%Y-%m-%dT%H:%M")
        print(air_date)

        if not title:
            error = "Title is required."

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                "INSERT INTO Episodes (show_id, title, air_date, url, description, created_by, updated_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (0, title, air_date, "http://example.com", description, g.user["id"], g.user["id"]),  # TODO show_id, url
            )
            db.commit()
            return redirect(url_for("scheduler.index"))

    return render_template("scheduler/create.html")


@bp.route("/<int:id>/update", methods=("GET", "POST"))
@login_required
def update(id):
    """Update a post if the current user is the author."""
    post = get_episode(id)

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        air_date = request.form["air_date"]
        audio_file = request.form["audio_file"]
        error = None

        air_date = datetime.strptime(air_date, "%Y-%m-%dT%H:%M")

        if not title:
            error = "Title is required."

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                "UPDATE post SET title = ?, air_date = ?, description = ? WHERE id = ?", (title, air_date, description, id)
            )
            db.commit()
            return redirect(url_for("scheduler.index"))

    return render_template("scheduler/update.html", post=post)


@bp.route("/<int:id>/delete", methods=("POST",))
@login_required
def delete(id):
    """Delete a post.

    Ensures that the post exists and that the logged in user is the
    author of the post.
    """
    get_episode(id)
    db = get_db()
    db.execute("DELETE FROM post WHERE id = ?", (id,))
    db.commit()
    return redirect(url_for("scheduler.index"))
