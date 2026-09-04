"""Variant of the weak baseline: prefer LEFT, then DOWN. Used only by tests."""

from game2048 import apply_move


def choose_move(board):
    for move in ("LEFT", "DOWN", "UP", "RIGHT"):
        if apply_move(board, move)[2]:
            return move
    return "LEFT"
