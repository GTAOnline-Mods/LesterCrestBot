import pickle

from config import config

def get_payloads():
    with open(config["payloads_file"], "rb") as f:
        while True:
            try:
                yield pickle.load(f)
            except EOFError:
                break

users = set(payload["user"] for payload in get_payloads())

for user in users:
    print(user, sum(1 for payload in get_payloads() if payload["user"] == user))
