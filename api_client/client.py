from enum import Enum
from string import Template
from typing import Type, TypeVar
from urllib.parse import urljoin

import pydantic
from requests import Request, Response, Session

from .response import Game, Mod, PaginatedResponse

ResponseType = TypeVar("ResponseType", bound=pydantic.BaseModel)
InnerResponseType = TypeVar("InnerResponseType", bound=pydantic.BaseModel)


class RequestMethod(Enum):
	GET = 'GET'


class ApiClient:
	_api_key: str
	_oauth_key: str
	_api_url: str

	_GET_MODS_ENDPOINT_TEMPLATE: Template = Template('games/${game_id}/mods')

	def __init__(self, api_key: str, oauth_key: str, api_url: str):
		self._api_key = api_key
		self._oauth_key = oauth_key
		self._api_url = api_url

	def _form_url(self, endpoint: str) -> str:
		return urljoin(self._api_url, endpoint)

	@staticmethod
	def _run_request(request: Request, response_type: Type[ResponseType]) -> ResponseType:
		with Session() as s:
			response: Response = s.send(request.prepare())
			response.raise_for_status()

			return response_type.parse_obj(response.json())

	def _create_request(self, method: RequestMethod, endpoint: str) -> Request:
		return Request(method.value, self._form_url(endpoint))

	@staticmethod
	def _add_offset(request: Request, offset: int = 0) -> None:
		request.params['_offset'] = offset

	def _add_api_key_authorization(self, request: Request) -> None:
		request.params['api_key'] = self._api_key

	def _add_oauth_authorization(self, request: Request) -> None:
		request.headers['Authorization'] = f'Bearer {self._oauth_key}'

	def _make_paginated_request(
			self, method: RequestMethod, endpoint: str, response_type: Type[InnerResponseType],
			use_api_key: bool = False, use_oauth: bool = False
	) -> list[InnerResponseType]:
		offset: int = 0
		rv: list[InnerResponseType] = []
		while offset is not None:
			request: Request = self._create_request(method, endpoint)
			if use_oauth:
				self._add_oauth_authorization(request)
			if use_api_key:
				self._add_api_key_authorization(request)
			self._add_offset(request, offset)
			paginated_response: PaginatedResponse[response_type] = self._run_request(
				request, PaginatedResponse[response_type]
			)
			rv.extend(paginated_response.data)
			offset = paginated_response.next_offset()
		return rv

	def get_games(self) -> list[Game]:
		return self._make_paginated_request(RequestMethod.GET, 'games', Game, use_api_key=True)

	def get_game_mods(self, game_id: int) -> list[Mod]:
		return self._make_paginated_request(
			RequestMethod.GET,
			type(self)._GET_MODS_ENDPOINT_TEMPLATE.substitute(game_id=game_id),
			Mod,
			use_api_key=True
		)

	def get_mod_subscriptions(self) -> list[Mod]:
		return self._make_paginated_request(RequestMethod.GET, 'me/subscribed', Mod, use_oauth=True)
