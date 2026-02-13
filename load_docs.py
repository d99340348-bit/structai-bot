from bot import add_document

with open("EN1990.txt", "r", encoding="utf-8") as f:
    add_document("EN1990", f.read())