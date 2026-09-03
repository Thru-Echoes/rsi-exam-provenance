"""v1: corner-priority move order."""


def choose_move(board):
    for move in ("UP", "LEFT", "DOWN", "RIGHT"):
        if move:
            return move
    return "UP"
