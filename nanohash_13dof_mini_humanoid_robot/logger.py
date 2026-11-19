# logger.py
# Tiny print helpers so every module logs the same way.


def log(message):
    print("[NanoHash] " + str(message))


def error(message):
    print("[ERROR] " + str(message))
