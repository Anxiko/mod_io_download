from typing import Callable, Generic, TypeVar

from pydantic import BaseModel, StrictInt, StrictStr
from pydantic.generics import GenericModel

ResponseType = TypeVar("ResponseType")


class PaginatedResponse(GenericModel, Generic[ResponseType]):
	data: list[ResponseType]
	result_count: StrictInt
	result_offset: StrictInt
	result_limit: StrictInt
	result_total: StrictInt

	def is_last(self) -> bool:
		return (self.result_offset + self.result_count) >= self.result_total

	def next_offset(self) -> int | None:
		rv: int = self.result_offset + self.result_limit
		if rv >= self.result_total:
			return None
		return rv


class Game(BaseModel):
	id: StrictInt
	name: StrictStr
	name_id: StrictStr

	@staticmethod
	def filter_by_name(name: str) -> Callable[['Game'], bool]:
		def f(game: 'Game') -> bool:
			return game.name_id == name

		return f


class Mod(BaseModel):
	id: StrictInt
	game_id: StrictInt
	name: StrictStr
	name_id: StrictStr
