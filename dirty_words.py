import json
import re
import time
import praw


def write_words():
    ws = list()
    with open("assets/DirtyWords.json", encoding="utf8") as f:
        words = json.load(f)["RECORDS"]
        count = 0
        for word in words:
            if word["language"] == "en":
                ws.append(word["word"])
    with open("assets/DirtyWords_en.txt", "w+") as f:
        f.write("\n".join(ws))


if __name__ == "__main__":
    with open("assets/DirtyWords_en.txt") as f:
        words = f.read().splitlines()
        word_patterns = [re.compile(r'\b({0})\b'.format(w), flags=re.IGNORECASE) for w in words]

        reddit = praw.Reddit("LCB")
        texts = [comment.body for comment in reddit.subreddit("gtaonline").comments(limit=None)]
        print(f"{len(texts)} comments found.")

        start_time = time.time()
        matches = 0
        for text in texts:
            matches += 1 if any(f" {word} " in f" {text} " for word in words) else 0
        print(f"{matches} matches, took {time.time() - start_time} seconds.")

        start_time = time.time()
        matches = 0
        for text in texts:
            matches += 1 if any(pattern.search(text) for pattern in word_patterns) else 0
        print(f"{matches} matches, took {time.time() - start_time} seconds.")
