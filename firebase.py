import firebase_admin
from firebase_admin import credentials, firestore

from stats import *

cred = credentials.Certificate("gtaonline-cf0ea-firebase-adminsdk-m40wm-c97b6484bf.json")
app = firebase_admin.initialize_app(cred)
db = firestore.client()

if __name__ == "__main__":
    mod_actions = db.collection("mod_actions")

    count = 0
    for payload in get_payloads():
        mod_actions.add(payload)
        count += 1

    print(count, "mod actions added to Firestore.")
