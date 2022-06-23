from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

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


WEEKDAYS = {
    0: "Sundays",
    1: "Mondays",
    2: "Tuesdays",
    3: "Wednesdays",
    4: "Thursdays",
    5: "Fridays",
    6: "Saturdays"
}

@bp.route("/")
@login_required
def index():
    """Show all the shows and episodes, most recent first."""
    # TODO don't get old ones
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT s.id, s.title, s.start_time, s.day_of_week, s.description, s.created_at, s.updated_at,"
        " creator.name AS creator, updater.name as updater"
        " FROM Shows s"
        " JOIN UserShowsJoin j ON j.show_id = s.id"
        " JOIN Users creator ON s.created_by = creator.id"
        " JOIN Users updater on s.updated_by = updater.id"
        " WHERE j.user_id = %s"
        " ORDER BY s.created_at DESC",
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
            " ORDER BY air_date ASC",
            (show["id"],),
        )
        episodes[show["id"]] = cur.fetchall()

    return render_template("scheduler/index.html", shows=shows, episodes=episodes, weekdays=WEEKDAYS)


def get_all_djs():
    """
    Return list of known djs.
    """
    db = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT id, name"
        " FROM Users"
        " ORDER BY name")
    return cur.fetchall()


def get_djs(show_id):
    """
    Return show djs.
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
        "SELECT *"
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
    """Create a new show"""
    if request.method == "POST":
        title = request.json["title"]
        description = request.json["description"]
        djs = request.json["djs"]
        day_of_week = request.json["day_of_week"]
        start_time = request.json["start_time"]
        error = None
        print(request.json)

        # TODO check for show collisions
        if not title:
            error = "title is required"
        elif not djs:
            error = "at least one dj is required"
        elif not description:
            error = "description is required"

        if error:
            return ({"error": error}, 400)

        db = get_db()
        cur = db.cursor()

        # create the Shows table entry
        cur.execute(
            "INSERT INTO Shows (title, day_of_week, start_time, description, created_by, updated_by)"
            " VALUES (%s, %s, %s, %s, %s, %s)"
            " RETURNING id",
            (title, day_of_week, start_time, description, g.user["id"], g.user["id"]))
        show_id = cur.fetchone()["id"]

        # add djs to the owners join table
        for user in djs:
            cur.execute(
                "INSERT INTO UserShowsJoin (user_id, show_id)"
                " VALUES (%s, %s)",
                (user, show_id))

        db.commit()
        return {
            "error": error,
            "redirect": url_for("scheduler.index")
        }

    djs = get_all_djs()
    return render_template("scheduler/create_show.html", djs=djs)


@bp.route("/shows/<int:id>/create_episode", methods=("GET", "POST"))
@login_required
def create_episode(id):
    """Create a new episode of show with id `id`"""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, title, day_of_week, start_time FROM Shows WHERE id = %s", (id,))
    show = cur.fetchone()

    # local to the station in Seattle
    now = datetime.now(tz=ZoneInfo("America/Los_Angeles"))
    days_offset = show["day_of_week"] - now.isoweekday()
    days_offset = days_offset if days_offset >= 0 else days_offset + 7
    next_show = now + timedelta(days=days_offset)

    # Get the upload url for B2 cloud storage
    info = InMemoryAccountInfo()  # store credentials, tokens and cache in memory
    session = B2Session(info)
    session.authorize_account("production", current_app.config["B2_KEY_ID"], current_app.config["B2_KEY"])
    upload = session.get_upload_url(current_app.config["B2_BUCKET_ID"])

    if request.method == "POST":
        title = request.json["title"]
        description = request.json["description"]
        air_date = request.json["air_date"]
        file_id = request.json["file_id"]
        error = None

        # TODO server-side validation of fields
        print(f"air_date: {air_date}")
        air_date = datetime.fromtimestamp(air_date)
        print(f"air_date: {air_date}")
        # TODO validate air date

        if not title:
            error = "Title is required."

        if error is not None:
            flash(error)
        else:
            cur.execute(
                "INSERT INTO Episodes (show_id, title, air_date, file_id, description, created_by, updated_by)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (id, title, air_date, file_id, description, g.user["id"], g.user["id"]),
            )
            db.commit()
            return redirect(url_for("scheduler.index"))

    return render_template("scheduler/create_episode.html", next_show=next_show, show=show, upload=upload, weekdays=WEEKDAYS)


@bp.route("/shows/<int:id>/update", methods=("GET", "POST"))
@login_required
def update_show(id):
    """Update a show."""
    show = get_show(id)
    all_djs = get_all_djs()
    current_djs = get_djs(id)

    print(f"all: {all_djs}")
    print(f"current: {current_djs}")

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

    return render_template("scheduler/update_show.html", show=show, current_djs=current_djs, all_djs=all_djs)


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
                (title, air_date, description, g.user["id"], id)
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
