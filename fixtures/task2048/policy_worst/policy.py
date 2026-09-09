"""Deliberately poor: the legal move with the smallest immediate merge score. Used only by tests."""

from game2048 import apply_move


def choose_move(board):
    best, best_gain = "UP", None
    for move in ("DOWN", "RIGHT", "LEFT", "UP"):
        _, gain, moved = apply_move(board, move)
        if moved and (best_gain is None or gain < best_gain):
            best, best_gain = move, gain
    return best
