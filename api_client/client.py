from enum import Enum
from io import FileIO
from string import Template
from typing import BinaryIO, Type, TypeVar
from urllib.parse import urljoin

import pydantic
from requests import Request, Response, Session

from .response import PaginatedResponse
from .models import Game, Mod, ModFile

ResponseType = TypeVar("ResponseType", bound=pydantic.BaseModel)
InnerResponseType = TypeVar("InnerResponseType", bound=pydantic.BaseModel)


class ApiClientException(Exception):
	pass


class ApiClientDownloadSizeException(ApiClientException):
	max_accepted: int
	actual: int

	def __init__(self, max_accepted: int, actual: int):
		self.max_accepted = max_accepted
		self.actual = actual
		super().__init__(f"Download size {self.actual} > max accepted {self.max_accepted}")


class ApiClient:
	_api_key: str
	_oauth_key: str
	_api_url: str

	_GET_GAME_ENDPOINT: Template = Template('games/${game_id}')
	_GET_MODS_ENDPOINT: Template = Template('games/${game_id}/mods')
	_GET_MOD_FILES_ENDPOINT: Template = Template('games/${game_id}/mods/${mod_id}/files')
	_DOWNLOAD_MOD_FILE_ENDPOINT: Template = Template('mods/file/${mod_file_id}')
	_FILE_MAX_SIZE: int = 500 * (1024 ** 2)  # 500MiB

	def __init__(self, api_key: str, oauth_key: str, api_url: str):
		self._api_key = api_key
		self._oauth_key = oauth_key
		self._api_url = api_url

	def _form_url(self, endpoint: str | Template, **kwargs) -> str:
		if isinstance(endpoint, Template):
			endpoint = endpoint.substitute(kwargs)
		elif kwargs:
			raise TypeError("Can't substitute from str endpoint")
		return urljoin(self._api_url, endpoint)

	@staticmethod
	def _run_request(request: Request, response_type: Type[ResponseType]) -> ResponseType:
		with Session() as s:
			response: Response = s.send(request.prepare())
			response.raise_for_status()

			return response_type.parse_obj(response.json())

	@classmethod
	def _run_file_request(cls, request: Request, fp: BinaryIO) -> None:
		with Session() as s:
			s.stream = True
			response: Response = s.send(request.prepare())
			response.raise_for_status()
			content_length: int = int(response.headers['Content-Length'])
			if content_length > cls._FILE_MAX_SIZE:
				raise ApiClientDownloadSizeException(
					max_accepted=cls._FILE_MAX_SIZE, actual=content_length
				)

			file_chunk: bytes
			for file_chunk in response.iter_content():
				fp.write(file_chunk)

	@staticmethod
	def _add_offset(request: Request, offset: int = 0) -> None:
		request.params['_offset'] = offset

	def _add_api_key_authorization(self, request: Request) -> None:
		request.params['api_key'] = self._api_key

	def _add_oauth_authorization(self, request: Request) -> None:
		request.headers['Authorization'] = f'Bearer {self._oauth_key}'

	def _run_paginated_request(
			self, request: Request, response_type: Type[InnerResponseType]
	) -> list[InnerResponseType]:
		offset: int = 0
		rv: list[InnerResponseType] = []
		while offset is not None:
			self._add_offset(request, offset)
			paginated_response: PaginatedResponse[response_type] = self._run_request(
				request, PaginatedResponse[response_type]
			)
			rv.extend(paginated_response.data)
			offset = paginated_response.next_offset()
		return rv

	def get_game_by_id(self, game_id: int) -> Game:
		request: Request = Request('GET', self._form_url(self._GET_GAME_ENDPOINT, game_id=game_id))
		self._add_api_key_authorization(request)
		return self._run_request(request, Game)

	def get_games(self) -> list[Game]:
		request: Request = Request('GET', self._form_url('games'))
		self._add_api_key_authorization(request)
		return self._run_paginated_request(request, Game)

	def get_game_mods(self, game_id: int) -> list[Mod]:
		request: Request = Request('GET', self._form_url(self._GET_MODS_ENDPOINT, game_id=game_id))
		self._add_api_key_authorization(request)
		return self._run_paginated_request(request, Mod)

	def get_mod_subscriptions(self) -> list[Mod]:
		request: Request = Request('GET', self._form_url('me/subscribed'))
		self._add_oauth_authorization(request)
		return self._run_paginated_request(request, Mod)

	def get_mod_files(self, game_id: int, mod_id: int) -> list[ModFile]:
		request: Request = Request(
			'GET', self._form_url(self._GET_MOD_FILES_ENDPOINT, game_id=game_id, mod_id=mod_id)
		)
		self._add_api_key_authorization(request)
		return self._run_paginated_request(request, ModFile)

	def download_mod_file(self, mod_file: ModFile, fp: BinaryIO) -> None:
		request: Request = Request(
			'GET', mod_file.download.binary_url
		)
		self._run_file_request(request, fp)
