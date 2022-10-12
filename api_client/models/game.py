from typing import Callable

from pydantic import BaseModel, StrictInt, StrictStr


class Game(BaseModel):
	id: StrictInt
	name: StrictStr
	name_id: StrictStr

	@staticmethod
	def filter_by_name(name: str) -> Callable[['Game'], bool]:
		def f(game: 'Game') -> bool:
			return game.name_id == name

		return f
