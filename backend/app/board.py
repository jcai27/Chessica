"""Wrapper around python-chess for move validation and FEN tracking."""

from __future__ import annotations

import chess


class Board:
    def __init__(self, inner: chess.Board) -> None:
        self._board = inner

    @classmethod
    def from_fen(cls, fen: str) -> "Board":
        return cls(chess.Board(fen))

    def to_fen(self) -> str:
        return self._board.fen()

    @property
    def active_color(self) -> str:
        return "w" if self._board.turn == chess.WHITE else "b"

    @property
    def fullmove(self) -> int:
        return self._board.fullmove_number

    def apply_uci(self, uci: str) -> None:
        move = chess.Move.from_uci(uci)
        if move not in self._board.legal_moves:
            raise ValueError(f"Illegal move: {uci}")
        self._board.push(move)

    def legal_moves(self) -> list[str]:
        return [move.uci() for move in self._board.legal_moves]

    def copy(self) -> "Board":
        return Board(self._board.copy(stack=True))

    @property
    def raw(self) -> chess.Board:
        return self._board
