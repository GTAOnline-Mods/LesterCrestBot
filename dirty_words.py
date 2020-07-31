import json


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
        texts = ["CausticPenguino is a butt LMFAO.", "Mods are gay.", "Badger is a motherfucking cocksucker."]
        for text in texts:
            print(text, any(word in text for word in words))
