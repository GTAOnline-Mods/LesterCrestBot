import json

if __name__ == "__main__":
    ws = list()
    with open("assets/DirtyWords.json", encoding="utf8") as f:
        words = json.load(f)["RECORDS"]
        count = 0
        for word in words:
            if word["language"] == "en":
                ws.append(word["word"])
    with open("assets/DirtyWords_en.txt", "w+") as f:
        f.write("\n".join(ws))
