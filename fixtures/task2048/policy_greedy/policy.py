"""One-ply greedy: the legal move with the largest immediate merge score. Used only by tests."""

from game2048 import apply_move


def choose_move(board):
    best, best_gain = "UP", -1
    for move in ("UP", "LEFT", "RIGHT", "DOWN"):
        _, gain, moved = apply_move(board, move)
        if moved and gain > best_gain:
            best, best_gain = move, gain
    return best
