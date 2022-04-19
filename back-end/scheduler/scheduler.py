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
@login_required
def index():
    """Show all the shows and episodes, most recent first."""
    # TODO don't get old ones
    db = get_db()
    shows = db.execute(
        "SELECT *"
        " FROM Shows"
        " JOIN UserShowsJoin ON UserShowsJoin.user_id = ? and UserShowsJoin.show_id = Shows.id"
        " ORDER BY created_at DESC"
        , (g.user["id"],)).fetchall()

    episodes = []
    for show in shows:
        episodes = db.execute(
            "SELECT *"
            " FROM Episodes"
            " WHERE show_id = ?"
            " ORDER BY air_date DESC",
            (show["id"],),
        ).fetchall()

    return render_template("scheduler/index.html", shows=shows, episodes=episodes)


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


def get_show(id):
    """Get show by id.

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



@bp.route("/shows/create", methods=("GET", "POST"))
@login_required
def create_show():
    """Create a new post for the current user."""
    db = get_db()
    # get all other djs
    djs = db.execute(
        "SELECT id, name"
        " FROM Users"
        " WHERE id != ?",
        (g.user["id"],)).fetchall()

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        co_hosts = request.form.get("co_hosts", None)
        error = None

        if not title:
            error = "title is required"

        if not description:
            error = "description is required"

        if error:
            flash(error)
        else:
            show_id = db.execute(
                "INSERT INTO Shows (title, description, created_by, updated_by)"
                " VALUES (?, ?, ?, ?)"
                " RETURNING id",
                (title, description, g.user["id"], g.user["id"]),
            ).fetchone()["id"]

            # add ourselves to the owners join table
            db.execute(
                "INSERT INTO UserShowsJoin (user_id, show_id)"
                " VALUES (?, ?)",
                (g.user["id"], show_id))

            # ...and add any co-hosts to the owners join table
            for user in co_hosts:
                db.execute(
                    "INSERT INTO UserShowsJoin (user_id, show_id)"
                    " VALUES (?, ?)",
                    (user, show_id))

            db.commit()
            return redirect(url_for("scheduler.index"))

    return render_template("scheduler/create_show.html", djs=djs)


@bp.route("/episodes/create", methods=("GET", "POST"))
@login_required
def create_episode():
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

    return render_template("scheduler/create_episode.html")


@bp.route("/shows/<int:id>/update", methods=("GET", "POST"))
@login_required
def update_show(id):
    """Update a show."""
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

    return render_template("scheduler/update_show.html", post=post)


@bp.route("/episodes/<int:id>/update", methods=("GET", "POST"))
@login_required
def update_episode(id):
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

    return render_template("scheduler/update_episode.html", post=post)


@bp.route("/episodes/<int:id>/delete", methods=("POST",))
@login_required
def delete_episode(id):
    """Delete a post.

    Ensures that the post exists and that the logged in user is the
    author of the post.
    """
    get_episode(id)
    db = get_db()
    db.execute("DELETE FROM post WHERE id = ?", (id,))
    db.commit()
    return redirect(url_for("scheduler.index"))
