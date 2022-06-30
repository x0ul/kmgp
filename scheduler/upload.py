import os
from b2sdk.v2 import InMemoryAccountInfo
from b2sdk.session import B2Session
import requests
from hashlib import sha1
from dotenv import load_dotenv

load_dotenv() # loads values from .env file into environment variables
B2_ID = os.environ["B2_UPLOAD_KEY_ID"]
B2_KEY = os.environ["B2_UPLOAD_KEY"]
B2_BUCKET_ID = os.environ["B2_BUCKET_ID"]

info = InMemoryAccountInfo()  # store credentials, tokens and cache in memory
session = B2Session(info)
session.authorize_account("production", B2_ID, B2_KEY)
upload = session.get_upload_url(B2_BUCKET_ID)
print(upload)

content = "this is the payload"
sha1 = sha1(content.encode()).hexdigest()
headers = {
    "Authorization": upload["authorizationToken"],
    "X-Bz-File-Name": "foo",
    "Content-Type": "b2/x-auto",
    "X-Bz-Content-Sha1": sha1
    }

rsp = requests.post(upload["uploadUrl"], headers=headers, data=content)

print(rsp.status_code)
print(rsp.text)
