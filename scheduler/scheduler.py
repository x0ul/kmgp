from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint
from flask import current_app
from flask import g
from flask import render_template
from flask import redirect
from flask import request
from flask import url_for
from werkzeug.exceptions import abort

from b2sdk.v2 import InMemoryAccountInfo
from b2sdk.session import B2Session

from scheduler.auth import login_required
from scheduler.db import get_db

import psycopg2  # for psycopg2.Error
from psycopg2 import sql

bp = Blueprint("scheduler", __name__)


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
            "SELECT e.id, e.title, e.air_date, e.description, e.original_filename, e.created_at, e.updated_at,"
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

    return render_template("scheduler/index.html", shows=shows, episodes=episodes)


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


@bp.route("/shows")
def get_shows():
    db = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT id, title, file_path FROM Shows"
    )
    cols = [desc[0] for desc in cur.description]
    vals = cur.fetchall()
    ret = []
    for val in vals:
        ret.append({c: v for c, v in zip(cols, val)})

    return {"shows": ret}


@bp.route("/episodes")
def get_upcoming_episodes():
    show_id = request.args.get("show_id")
    db = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT id, title, air_date, file_id"
        " FROM Episodes"
        " WHERE show_id = %s"
        " AND air_date > CURRENT_TIMESTAMP",
        (show_id,)
    )

    cols = [desc[0] for desc in cur.description]
    vals = cur.fetchall()
    ret = []
    for val in vals:
        ep = {c: v for c, v in zip(cols, val)}
        ep["air_date"] = int(ep["air_date"].replace(tzinfo=timezone.utc).timestamp())
        ret.append(ep)

    return {"show_id": show_id, "episodes": ret}


@bp.route("/shows/create", methods=("GET", "POST"))
@login_required
def create_show():
    """Create a new show"""
    if request.method == "POST":
        post = {}
        try:
            post["title"] = request.json["title"]
            post["day_of_week"] = request.json["day_of_week"]
            post["start_time"] = request.json["start_time"]
            post["djs"] = request.json["djs"]
            post["description"] = request.json["description"]
            post["file_path"] = request.json["file_path"]
        except KeyError as e:
            error = f"{e.args[0].replace('_', ' ')} is required"
            return ({"error": error}, 400)
        for field, val in post.items():
            if not val:
                error = f"{field.replace('_', ' ')} is required"
                return ({"error": error}, 400)

        db = get_db()
        cur = db.cursor()

        # create the Shows table entry
        try:
            cur.execute(
                """
                INSERT INTO Shows (title, day_of_week, start_time, description, file_path, created_by, updated_by)
                VALUES (%(title)s, %(day_of_week)s, %(start_time)s, %(description)s, %(file_path)s, %(user_id)s, %(user_id)s)
                RETURNING id;
                """,
                {
                    "title": post["title"],
                    "day_of_week": post["day_of_week"],
                    "start_time": post["start_time"],
                    "description": post["description"],
                    "file_path": post["file_path"],
                    "user_id": g.user["id"]
                })
            show_id = cur.fetchone()["id"]

            # add djs to the owners join table
            for user in post["djs"]:
                cur.execute(
                    """
                    INSERT INTO UserShowsJoin (user_id, show_id)
                    VALUES (%(user_id)s, %(show_id)s);
                    """,
                    {
                        "user_id": user,
                        "show_id": show_id
                    })

            db.commit()
        except psycopg2.errors.UniqueViolation as e:
            if e.diag.constraint_name == "uidx_show_timeslot":
                return ({"error": "another show already exists in this timeslot"}, 400)
        except psycopg2.Error as e:
            return ({"error": e.diag.message_detail}, 400)

        return {"redirect": url_for("scheduler.index")}

    # GET request
    djs = get_all_djs()
    return render_template("scheduler/create_show.html", djs=djs)


@bp.route("/shows/<int:id>/create_episode", methods=("GET", "POST"))
@login_required
def create_episode(id):
    """Create a new episode of show with id `id`"""
    db = get_db()
    cur = db.cursor()
    show = get_show(id)

    # local to the station in Seattle
    now = datetime.now(tz=ZoneInfo("America/Los_Angeles"))
    weekday_to_isoweekday = {
        "Monday": 1,
        "Tuesday": 2,
        "Wednesday": 3,
        "Thursday": 4,
        "Friday": 5,
        "Saturday": 6,
        "Sunday": 7
    }
    days_offset = weekday_to_isoweekday[show["day_of_week"]] - now.isoweekday()
    days_offset = days_offset if days_offset >= 0 else days_offset + 7
    next_episode = now + timedelta(days=days_offset)
    if days_offset == 0 and (now + timedelta(hours=1)).time() > show["start_time"]:  # allow uploads up to one hour before air
        next_episode += timedelta(days=7)

    # Get the upload url for B2 cloud storage
    info = InMemoryAccountInfo()  # store credentials, tokens and cache in memory
    session = B2Session(info)
    session.authorize_account("production", current_app.config["B2_UPLOAD_KEY_ID"], current_app.config["B2_UPLOAD_KEY"])
    upload = session.get_upload_url(current_app.config["B2_BUCKET_ID"])

    if request.method == "POST":
        post = {}
        required_fields = ("title", "air_date", "file_id", "original_filename")
        try:
            post["title"] = request.json["title"]
            post["description"] = request.json["description"]
            post["air_date"] = datetime.strptime(request.json["air_date"], "%Y-%m-%d")
            post["file_id"] = request.json["file_id"]
            post["original_filename"] = request.json["original_filename"]
        except KeyError as e:
            error = f"{e.args[0].replace('_', ' ')} is required"
            return ({"error": error}, 400)
        except BaseException as e:
            return ({"error": str(e)}, 400)

        for field in required_fields:
            if field not in post:
                error = f"{field.replace('_', ' ')} is required"
                return ({"error": error}, 400)

        # validate that air date matches show schedule
        if weekday_to_isoweekday[show["day_of_week"]] != post["air_date"].isoweekday():
            return ({"error": "air date does not match schedule"}, 400)
        air_date = datetime.combine(post["air_date"],
                                    show["start_time"],
                                    tzinfo=ZoneInfo("America/Los_Angeles"))

        if air_date < datetime.now(tz=ZoneInfo("America/Los_Angeles")) + timedelta(hours=1):
            return ({"error": "air date is in the past"}, 400)

        try:
            cur.execute(
                """
            INSERT INTO Episodes (show_id, title, air_date, file_id, original_filename, description, created_by, updated_by)
            VALUES (%(show_id)s, %(title)s, %(air_date)s, %(file_id)s, %(original_filename)s, %(description)s, %(user)s, %(user)s);
            """,
                {
                    "show_id": id,
                    "title": post["title"],
                    "air_date": air_date,
                    "file_id": post["file_id"],
                    "original_filename": post["original_filename"],
                    "description": post["description"],
                    "user": g.user["id"]
                },
            )
            db.commit()
        except psycopg2.errors.UniqueViolation as e:
            if e.diag.constraint_name == "episodes_air_date_key":
                return ({"error": "another episode already exists in this timeslot"}, 400)
        except psycopg2.Error as e:
            return ({"error": e.diag.message_detail}, 400)

        return {"redirect": url_for("scheduler.index")}

    return render_template("scheduler/create_episode.html", next_episode=next_episode, show=show, upload=upload)


@bp.route("/shows/<int:id>/update", methods=("GET", "POST"))
@login_required
def update_show(id):
    """Update a show."""
    show = get_show(id)
    all_djs = get_all_djs()
    current_djs = get_djs(id)

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        error = None

        if not title:
            error = "Title is required."

        if error is not None:
            pass
        else:
            db = get_db()
            cur = db.cursor()
            cur.execute(
                "UPDATE Shows SET title = %s, description = %s, updated_by = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (title, description, g.user["id"], id)
            )
            db.commit()
            return redirect(url_for("scheduler.index"))

    return render_template("scheduler/update_show.html", show=show, current_djs=current_djs, all_djs=all_djs)


@bp.route("/episodes/<int:id>/delete", methods=("POST",))
@login_required
def delete_episode(id):
    """
    Delete an episode.
    """
    get_episode(id)
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM Episodes WHERE id = %s", (id,))
    db.commit()
    return redirect(url_for("scheduler.index"))
