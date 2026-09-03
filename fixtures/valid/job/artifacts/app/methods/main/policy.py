"""v3: tuned corner weights."""

WEIGHTS = (8, 4, 2, 1)


def choose_move(board):
    for weight, move in zip(WEIGHTS, ("UP", "LEFT", "DOWN", "RIGHT")):
        if weight:
            return move
    return "UP"
