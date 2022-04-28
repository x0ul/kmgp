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
    """Show all the programs and shows, most recent first."""
    # TODO don't get old ones
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT p.id, p.title, p.description, p.created_at, p.updated_at,"
        " creator.name AS creator, updater.name as updater"
        " FROM Programs p"
        " JOIN UserProgramsJoin j ON j.program_id = p.id"
        " JOIN Users creator ON p.created_by = creator.id"
        " JOIN Users updater on p.updated_by = updater.id"
        " WHERE j.user_id = %s"
        " ORDER BY p.created_at DESC",
        (g.user["id"],))
    programs = cur.fetchall()

    shows = {}
    for program in programs:
        cur.execute(
            "SELECT *"
            " FROM Shows"
            " WHERE program_id = %s"
            " ORDER BY air_date DESC",
            (program["id"],),
        )
        shows[program["id"]] = cur.fetchall()


    return render_template("scheduler/index.html", programs=programs, shows=shows)


def get_show(id):
    """Get an show by id.

    TODO use the join table to check if the current auth'd user is an owner.

    :param id: id of show to get
    TODO :param check_user: require the current user to be an owner
    :return: the show
    :raise 404: if an show with the given id doesn't exist
    :raise 403: if the current user isn't an owner
    """
    post = (
        get_db()
        .execute(
            "SELECT e.id, program_id, air_date, url, created_at, updated_at, description, title"
            " FROM Shows e"
            " WHERE e.id = %s",
            (id,),
        )
        .fetchone()
    )

    if not post:
        abort(404, f"Post id {id} doesn't exist.")

    if check_author and post["author_id"] != g.user["id"]:
        abort(403)

    return post


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


def get_hosts(program_id):
    """
    Return program hosts.
    """
    db = get_db()
    cur = db.cursor()

    cur.execute(
        "SELECT user_id FROM UserProgramsJoin"
        " WHERE program_id = %s",
        (program_id,))
    return cur.fetchall()


def get_program(id):
    """Get program by id.

    TODO use the join table to check if the current auth'd user is an owner.

    :param id: id of program to get
    TODO :param check_user: require the current user to be an owner
    :return: the program
    :raise 404: if an program with the given id doesn't exist
    :raise 403: if the current user isn't an owner
    """
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT *"
        " FROM Programs"
        " WHERE id = %s",
        (id,))
    program = cur.fetchone()

    if not program:
        abort(404, f"Program id {id} doesn't exist.")

    return program


def get_show(id):
    """Get an show by id.

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
        "SELECT e.id, program_id, air_date, url, created_at, updated_at, description, title"
        " FROM Shows e"
        " WHERE e.id = %s",
        (id,))

    show = cur.fetchone()

    if not show:
        abort(404, f"Show id {id} doesn't exist.")

    return show


@bp.route("/programs/create", methods=("GET", "POST"))
@login_required
def create_program():
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

            # create the Programs table entry
            cur.execute(
                "INSERT INTO Programs (title, description, created_by, updated_by)"
                " VALUES (%s, %s, %s, %s)"
                " RETURNING id",
                (title, description, g.user["id"], g.user["id"]))
            program_id = cur.fetchone()["id"]

            # add ourselves to the owners join table
            cur.execute(
                "INSERT INTO UserProgramsJoin (user_id, program_id)"
                " VALUES (%s, %s)",
                (g.user["id"], program_id))

            # ...and add any co-hosts to the owners join table
            for user in co_hosts:
                cur.execute(
                    "INSERT INTO UserProgramsJoin (user_id, program_id)"
                    " VALUES (%s, %s)",
                    (user, program_id))

            db.commit()
            return redirect(url_for("scheduler.index"))

    djs = get_other_djs(g.user["id"])
    return render_template("scheduler/create_program.html", djs=djs)


@bp.route("/programs/<int:id>/create_show", methods=("GET", "POST"))
@login_required
def create_show(id):
    """Create a new post for the current user."""
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, title FROM Programs WHERE id = %s", (id,))
    program = cur.fetchone()

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
                "INSERT INTO Shows (program_id, title, air_date, url, description, created_by, updated_by)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (id, title, air_date, "http://example.com", description, g.user["id"], g.user["id"]),  # TODO url of audio file
            )
            db.commit()
            return redirect(url_for("scheduler.index"))

    return render_template("scheduler/create_show.html", program=program)


@bp.route("/programs/<int:id>/update", methods=("GET", "POST"))
@login_required
def update_program(id):
    """Update a program."""
    program = get_program(id)
    djs = get_other_djs(g.user["id"])
    hosts = get_hosts(id)

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
                "UPDATE post SET title = %s, air_date = %s, description = %s WHERE id = %s", (title, air_date, description, id)
            )
            db.commit()
            return redirect(url_for("scheduler.index"))

    return render_template("scheduler/update_program.html", program=program, djs=djs, hosts=hosts)


# TODO the file
@bp.route("/shows/<int:id>/update", methods=("GET", "POST"))
@login_required
def update_show(id):
    show = get_show(id)

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
                "UPDATE Shows"
                " SET title = %s, air_date = %s, description = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s"
                " WHERE id = %s",
                (title, air_date, description, id, g.user["id"])
            )
            db.commit()
            return redirect(url_for("scheduler.index"))

    return render_template("scheduler/update_show.html", show=show)


@bp.route("/shows/<int:id>/delete", methods=("POST",))
@login_required
def delete_show(id):
    """Delete a post.

    Ensures that the post exists and that the logged in user is the
    author of the post.
    """
    get_show(id)
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM Shows WHERE id = %s", (id,))
    db.commit()
    return redirect(url_for("scheduler.index"))
