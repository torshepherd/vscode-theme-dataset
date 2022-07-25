import json
from os import path, readlink
import csv

PATH = readlink(__file__) if path.islink(__file__) else __file__
SRC_DIR = path.dirname(PATH)
TOP_DIR = path.dirname(SRC_DIR)
LOG_DIR = path.join(TOP_DIR, "log")
DATA_DIR = path.join(TOP_DIR, "data")


l = []
with open(path.join(DATA_DIR, "themes.json"), "r") as theme_input_file:
    l: list[dict] = json.load(theme_input_file)


with open(path.join(DATA_DIR, "themes.csv"), "w", encoding="utf-8") as theme_csv_file:
    w = csv.writer(theme_csv_file, delimiter=",")
    w.writerow(("name", "uiTheme", "path", "format", "theme"))
    for row in l:
        csv_row = (
            row["name"],
            row["theme"]["uiTheme"],
            row["theme"]["path"],
            row["theme"]["format"],
            row["theme"]["contents"],
        )
        w.writerow(csv_row)


# Metadata

l = []
with open(path.join(DATA_DIR, "theme_metadata.json"), "r") as theme_input_file:
    l: list[dict] = json.load(theme_input_file)


with open(
    path.join(DATA_DIR, "theme_metadata.csv"), "w", encoding="utf-8"
) as theme_csv_file:
    w = csv.writer(theme_csv_file, delimiter=",")
    w.writerow(l[0].keys())
    for row in l:
        w.writerow((row[k] for k in row.keys()))
