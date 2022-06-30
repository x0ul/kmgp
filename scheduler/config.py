import os
from dotenv import load_dotenv


class Config:
    """
    Populate values from env or a .env file (via python-dotenv).

    Values set in the .env file will not override env vars.
    """
    load_dotenv()
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DATABASE_URL = os.environ.get("DATABASE_URL")
    B2_UPLOAD_KEY_ID = os.environ.get("B2_UPLOAD_KEY_ID")
    B2_UPLOAD_KEY = os.environ.get("B2_UPLOAD_KEY")
    B2_BUCKET_ID = os.environ.get("B2_BUCKET_ID")
