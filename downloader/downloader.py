import datetime
import logging
import os
import requests
import shutil
from b2sdk.v2 import InMemoryAccountInfo
from b2sdk.v2 import B2Api
from dotenv import load_dotenv


def b2_download_file(b2_api, b2_file_id, output_filename):
    pass
    # b2_api.download_file_by_id(b2_file_id).save_to(output_filename)


def get_shows(url):
    """
    Get list of shows known to the scheduler back-end
    """

    r = requests.get(url)
    if r.status_code == 200:
        return r.json()["shows"]
    else:
        # best effort at logging the error
        error = "unknown"
        try:
            error = r.json()["error"]
        except BaseException:
            pass

        logging.error(f"error in get_shows; http status {r.status_code}, error: {error}")
        return {}


def get_upcoming_episodes(url, show_id):
    """
    Get list of upcoming episodes for a given show.
    """
    pass
    r = requests.get(url, params={"show_id": show_id)
    if r.status_code == 200:
        return r.json()["episodes"]
    else:
        # best effort at logging the error
        error = "unknown"
        try:
            error = r.json()["error"]
        except BaseException:
            pass

        logging.error(f"error in get_upcoming_episodes; http status {r.status_code}, error: {error}")
        return {}



def run_once():
    logging.info("starting episode puller")
    load_dotenv()  # loads values from .env file into environment variables
    DOWNLOAD_PATH = os.environ["SHOW_DOWNLOAD_PATH"]
    B2_KEY_ID = os.environ["B2_DOWNLOAD_KEY_ID"]
    B2_KEY = os.environ["B2_DOWNLOAD_KEY"]
    GET_SHOWS_URL = os.environ["GET_SHOWS_URL"]
    GET_EPISODES_URL = os.environ["GET_EPISODES_URL"]

    shows = get_shows(GET_SHOWS_URL)
    print(shows)

    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_KEY)

    for show in shows:
        episodes = get_upcoming_episodes(GET_EPISODES_URL, show["id"])
        show_path = os.path.join(DOWNLOAD_PATH, show["id"])
        os.makedirs(show_path, exist_ok=True)

        # download upcoming episode audio files
        for episode in episodes:
            episode_path = os.path.join(show_path, episode["id"])
            # TODO determine if already downloaded
            logging.info(f"downloading [{show['title']}]: [{episode['title']}] to {episode_path}")
            b2_download_file(b2_api, episode["file_id"], episode_path)
            # TODO report back download status

        # copy the next episode of this show to where station playlist expects
        # symlinks in windows are weird, so copy instead of linking
        if episodes:
            # TODO skip if it's the same file
            next_episode = min(episodes, key=lambda ep: ep["air_date"])
            next_episode_path = os.path.join(show_path, next_episode["id"])
            logging.info(f"[{show['title']}]: [{episode['title']}] is next up, copying {next_episode_path} to {show['file_path']}")
            shutil.copyfile(next_episode_path, show["file_path"])
            # TODO report back next up status

    # clean out old files
    logging.info("deleting old episode files from the download/staging directory")
    today = datetime.date.today()
    a_month_ago = today - datetime.timedelta(days=30)
    for root, dirs, files in os.walk(DOWNLOAD_PATH):
        for f in files:
            f_path = os.path.join(root, f)
            created_at = datetime.date.fromtimestamp(os.path.getctime(f_path))
            if created_at < a_month_ago:
                os.unlink(f_path)

    # TODO report successful run

# TODO do something with old episode files
# create/update the symbolic link for each show that points at the next episode
# report to webapp which episodes were downloaded, which episode is next up to play
# send logs somewhere


if __name__ == "__main__":
    run_once()
