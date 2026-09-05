"""v2: depth-2 lookahead (too slow; reverted)."""


def choose_move(board):
    best = None
    for move in ("UP", "LEFT", "DOWN", "RIGHT"):
        for follow_up in ("UP", "LEFT"):
            best = best or (move, follow_up)
    return best[0] if best else "UP"
