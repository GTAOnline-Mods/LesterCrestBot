import pickle
import re
from typing import Any, Dict, List, Generator, Iterable

from config import config

POST_URL_PATTERN = re.compile(
    r"/r(?:/(?P<subreddit>\w+))/comments(?:/(?P<submission>\w+))(?:/\w+/(?P<comment>\w+))?")


def get_payloads() -> Generator[Any, None, None]:
    with open(config["payloads_file"], "rb") as f:
        while True:
            try:
                yield pickle.load(f)
            except EOFError:
                break


def get_actions_by_user(user: str = "") -> Dict:
    return split_actions_by_user(get_payloads(), user)


def get_users_action_count(user_actions: Dict[str, Any]) -> Dict:
    return {user: len(actions) for user, actions in user_actions.items()}


def split_actions_by_user(payloads: Iterable[Dict[str, Any]], user: str = "") -> Dict:
    users = dict()
    for payload in payloads:
        if user and payload["user"] != user:
            continue

        if payload["user"] not in users:
            users[payload["user"]] = list()

        users[payload["user"]].append(payload)
    return users


def get_actions_by_type() -> Dict:
    return split_actions_by_type(get_payloads())


def split_actions_by_type(payloads: Iterable[Dict[str, Any]]) -> Dict:
    types = {
        "comments": list(),
        "submissions": list()
    }

    for payload in payloads:
        match = POST_URL_PATTERN.search(payload["item"])
        if match and match.group("comment"):
            types["comments"].append(payload)
        elif match:
            types["submissions"].append(payload)

    return types


if __name__ == "__main__":
    payloads = [p for p in get_payloads()]

    for t, payloads in split_actions_by_type(payloads).items():
        actions_by_users = split_actions_by_user(payloads)
        print(t, get_users_action_count(actions_by_users))

    print(get_users_action_count(split_actions_by_user(payloads)))
