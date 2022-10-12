from typing import Generic, TypeVar

from pydantic import StrictInt
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
