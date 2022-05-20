from datetime import datetime

from flask import Blueprint
from flask import current_app
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from werkzeug.exceptions import abort

from b2sdk.v2 import InMemoryAccountInfo
from b2sdk.session import B2Session

from scheduler.auth import login_required
from scheduler.db import get_db

bp = Blueprint("scheduler", __name__)


@bp.route("/")
@login_required
def index():
    """Show all the shows and episodes, most recent first."""
    # TODO don't get old ones
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT p.id, p.title, p.description, p.created_at, p.updated_at,"
        " creator.name AS creator, updater.name as updater"
        " FROM Shows p"
        " JOIN UserShowsJoin j ON j.show_id = p.id"
        " JOIN Users creator ON p.created_by = creator.id"
        " JOIN Users updater on p.updated_by = updater.id"
        " WHERE j.user_id = %s"
        " ORDER BY p.created_at DESC",
        (g.user["id"],))
    shows = cur.fetchall()

    episodes = {}
    for show in shows:
        cur.execute(
            "SELECT e.id, e.title, e.air_date, e.description, e.created_at, e.updated_at,"
            " creator.name as creator, updater.name as updater"
            " FROM Episodes e"
            " JOIN Users creator ON e.created_by = creator.id"
            " JOIN Users updater on e.updated_by = updater.id"
            " WHERE e.show_id = %s"
            " AND e.air_date >= CURRENT_TIMESTAMP"
            " ORDER BY air_date DESC",
            (show["id"],),
        )
        episodes[show["id"]] = cur.fetchall()


    return render_template("scheduler/index.html", shows=shows, episodes=episodes)


def get_other_djs(my_id):
    """
    Return other djs, excluding myself
    """
    db = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT id, name"
        " FROM Users"
        " WHERE id != %s"
        " ORDER BY name",
        (g.user["id"],))
    djs = cur.fetchall()

    return djs


def get_hosts(show_id):
    """
    Return show hosts.
    """
    db = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT user_id FROM UserShowsJoin"
        " WHERE show_id = %s",
        (show_id,))
    return cur.fetchall()


def get_show(id):
    """Get show by id.

    TODO use the join table to check if the current auth'd user is an owner.

    :param id: id of show to get
    TODO :param check_user: require the current user to be an owner
    :return: the show
    :raise 404: if an show with the given id doesn't exist
    :raise 403: if the current user isn't an owner
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT *"
        " FROM Shows"
        " WHERE id = %s",
        (id,))
    show = cur.fetchone()

    if not show:
        abort(404, f"Show id {id} doesn't exist.")

    return show


def get_episode(id):
    """Get an episode by id.

    TODO use the join table to check if the current auth'd user is an owner.

    :param id: id of episode to get
    TODO :param check_user: require the current user to be an owner
    :return: the episode
    :raise 404: if an episode with the given id doesn't exist
    :raise 403: if the current user isn't an owner
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT e.id, show_id, air_date, url, created_at, updated_at, description, title"
        " FROM Episodes e"
        " WHERE e.id = %s",
        (id,))

    episode = cur.fetchone()

    if not episode:
        abort(404, f"episode id {id} doesn't exist.")

    return episode


@bp.route("/shows/create", methods=("GET", "POST"))
@login_required
def create_show():
    """Create a new post for the current user."""
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        co_hosts = request.form.get("co_hosts", [])
        error = None

        if not title:
            error = "title is required"

        if not description:
            error = "description is required"

        if error:
            flash(error)
        else:
            db = get_db()
            cur = db.cursor()

            # create the Shows table entry
            cur.execute(
                "INSERT INTO Shows (title, description, created_by, updated_by)"
                " VALUES (%s, %s, %s, %s)"
                " RETURNING id",
                (title, description, g.user["id"], g.user["id"]))
            show_id = cur.fetchone()["id"]

            # add ourselves to the owners join table
            cur.execute(
                "INSERT INTO UserShowsJoin (user_id, show_id)"
                " VALUES (%s, %s)",
                (g.user["id"], show_id))

            # ...and add any co-hosts to the owners join table
            for user in co_hosts:
                cur.execute(
                    "INSERT INTO UserShowsJoin (user_id, show_id)"
                    " VALUES (%s, %s)",
                    (user, show_id))

            db.commit()
            return redirect(url_for("scheduler.index"))

    djs = get_other_djs(g.user["id"])
    return render_template("scheduler/create_show.html", djs=djs)


@bp.route("/shows/<int:id>/create_episode", methods=("GET", "POST"))
@login_required
def create_episode(id):
    """Create a new post for the current user."""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, title FROM Shows WHERE id = %s", (id,))
    show = cur.fetchone()

    # Get the upload url for B2 cloud storage
    info = InMemoryAccountInfo()  # store credentials, tokens and cache in memory
    session = B2Session(info)
    session.authorize_account("production", current_app.config["B2_KEY_ID"], current_app.config["B2_KEY"])
    upload = session.get_upload_url(current_app.config["B2_BUCKET_ID"])

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
            cur.execute(
                "INSERT INTO Episodes (show_id, title, air_date, url, description, created_by, updated_by)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (id, title, air_date, "http://example.com", description, g.user["id"], g.user["id"]),  # TODO url of audio file
            )
            db.commit()
            return redirect(url_for("scheduler.index"))

    return render_template("scheduler/create_episode.html", show=show, upload=upload)


@bp.route("/shows/<int:id>/update", methods=("GET", "POST"))
@login_required
def update_show(id):
    """Update a show."""
    show = get_show(id)
    djs = get_other_djs(g.user["id"])
    hosts = get_hosts(id)

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        error = None

        if not title:
            error = "Title is required."

        if error is not None:
            flash(error)
        else:
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "UPDATE Shows SET title = %s, description = %s, updated_by = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (title, description, g.user["id"], id)
            )
            db.commit()
            return redirect(url_for("scheduler.index"))

    return render_template("scheduler/update_show.html", show=show, djs=djs, hosts=hosts)


# TODO the file
@bp.route("/episodes/<int:id>/update", methods=("GET", "POST"))
@login_required
def update_episode(id):
    episode = get_episode(id)

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
            cur = db.cursor()
            cur.execute(
                "UPDATE Episodes"
                " SET title = %s, air_date = %s, description = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s"
                " WHERE id = %s",
                (title, air_date, description, id, g.user["id"])
            )
            db.commit()
            return redirect(url_for("scheduler.index"))

    return render_template("scheduler/update_episode.html", episode=episode)


@bp.route("/episodes/<int:id>/delete", methods=("POST",))
@login_required
def delete_episode(id):
    """Delete a post.

    Ensures that the post exists and that the logged in user is the
    author of the post.
    """
    get_episode(id)
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM Episodes WHERE id = %s", (id,))
    db.commit()
    return redirect(url_for("scheduler.index"))
