import pickle
from typing import Dict

from config import config


def get_payloads():
    with open(config["payloads_file"], "rb") as f:
        while True:
            try:
                yield pickle.load(f)
            except EOFError:
                break


def get_actions_by_user(user: str = "") -> Dict:
    users = dict()
    for payload in get_payloads():
        if user and payload["user"] != user:
            continue
        users[payload["user"]] = users.get(payload["user"], 0) + 1
    return users


if __name__ == "__main__":
    for user, actions in get_actions_by_user().items():
        print(user, actions)
