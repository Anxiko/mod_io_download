from enum import Enum
from typing import Type, TypeVar
from urllib.parse import urljoin

import pydantic
from requests import Request, Response, Session

from .response import Game, PaginatedResponse

ResponseType = TypeVar("ResponseType", bound=pydantic.BaseModel)
InnerResponseType = TypeVar("InnerResponseType", bound=pydantic.BaseModel)


class RequestMethod(Enum):
	GET = 'GET'


class ApiClient:
	_api_key: str
	_api_url: str

	def __init__(self, api_key: str, api_url: str):
		self._api_key = api_key
		self._api_url = api_url

	def _form_url(self, endpoint: str) -> str:
		return urljoin(self._api_url, endpoint)

	def _run_request(self, request: Request, response_type: Type[ResponseType]) -> ResponseType:
		with Session() as s:
			response: Response = s.send(request.prepare())
			response.raise_for_status()

			return response_type.parse_obj(response.json())

	def _create_request(self, method: RequestMethod, endpoint: str) -> Request:
		return Request(method.value, self._form_url(endpoint))

	@staticmethod
	def _add_offset(request: Request, offset: int = 0) -> None:
		request.params["_offset"] = offset

	def _add_validation(self, request: Request) -> None:
		request.params["api_key"] = self._api_key

	def _make_paginated_request(
			self, method: RequestMethod, endpoint: str, response_type: Type[InnerResponseType]
	) -> list[InnerResponseType]:
		offset: int = 0
		rv: list[InnerResponseType] = []
		while offset is not None:
			request: Request = self._create_request(method, endpoint)
			self._add_validation(request)
			self._add_offset(request, offset)
			paginated_response: PaginatedResponse[response_type] = self._run_request(
				request, PaginatedResponse[response_type]
			)
			rv.extend(paginated_response.data)
			offset = paginated_response.next_offset()
		return rv

	def get_games(self) -> list[Game]:
		return self._make_paginated_request(RequestMethod.GET, 'games', Game)
