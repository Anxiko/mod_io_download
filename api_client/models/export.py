from pydantic import BaseModel

from .game import Game
from .mod import ModWithModfile


class SubscriptionsForGame(BaseModel):
	game: Game
	mods: list[ModWithModfile]


class SubscriptionsExport(BaseModel):
	subscriptions: dict[str, SubscriptionsForGame]
