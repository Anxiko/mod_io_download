import asyncio
import logging
import sys
from string import Template
from typing import Awaitable, BinaryIO, Callable, Optional, Type, TypeVar
from urllib.parse import urljoin

import httpx
import pydantic
from requests import Request, Response, Session
from tqdm.asyncio import tqdm

from logger import get_logger
from .models.game import Game
from .models.mod import Mod
from .models.mod_file import ModFile
from .models.platform import TargetPlatform
from .response import PaginatedResponse

logger: logging.Logger = get_logger(__name__)

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

	_GET_MOD_FILE_ENDPOINT: Template = Template('games/${game_id}/mods/${mod_id}/files/${mod_file_id}')
	_FILE_MAX_SIZE: int = 500 * (1024 ** 2)  # 500MiB

	def __init__(
			self, api_key: str, oauth_key: str, api_url: str
	):
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

	@staticmethod
	def _add_platform(request: Request, platform: TargetPlatform) -> None:
		request.headers['X-Modio-Platform'] = platform.value

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

	def get_games(self, name_id: Optional[str] = None) -> list[Game]:
		logger.info(f"Getting all games, {name_id=}")
		request: Request = Request('GET', self._form_url('games'))
		if name_id is not None:
			request.params['name_id'] = name_id
		self._add_api_key_authorization(request)
		return self._run_paginated_request(request, Game)

	def get_mod_subscriptions(
			self, game_id: Optional[int] = None, platform: TargetPlatform = None
	) -> list[Mod]:
		logger.info(f"Getting mod subscriptions, {game_id=}, {platform=}")
		request: Request = Request('GET', self._form_url('me/subscribed'))
		if game_id is not None:
			request.params['game_id'] = game_id

		if platform:
			self._add_platform(request, platform)

		self._add_oauth_authorization(request)
		return self._run_paginated_request(request, Mod)

	def get_mod_file_by_id(self, game_id: int, mod_id: int, mod_file_id: int) -> ModFile:
		logger.info(f"Getting mod file for {game_id=}, {mod_id=}, {mod_file_id=}")
		request: Request = Request(
			'GET',
			self._form_url(
				self._GET_MOD_FILE_ENDPOINT, game_id=game_id, mod_id=mod_id, mod_file_id=mod_file_id
			)
		)
		self._add_api_key_authorization(request)
		return self._run_request(request, ModFile)

	async def _get_mod_file_by_id_async(
			self, async_client: httpx.AsyncClient, game_id: int, mod_id: int, mod_file_id: int,
			callback: Callable[[], None]
	) -> ModFile:
		url: str = self._form_url(self._GET_MOD_FILE_ENDPOINT, game_id=game_id, mod_id=mod_id, mod_file_id=mod_file_id)
		response: httpx.Response = await async_client.get(url, params=dict(api_key=self._api_key))
		response.raise_for_status()
		mod_file: ModFile = ModFile.parse_obj(response.json())
		callback()
		return mod_file

	async def get_mod_files_concurrently(
			self, game_id: int, mod_and_mod_file_tuples: list[tuple[int, int]]
	) -> list[ModFile]:
		async with httpx.AsyncClient() as client:
			tasks: list[Awaitable[ModFile]] = [
				self._get_mod_file_by_id_async(client, game_id, mod_id, mod_file_id, lambda: None)
				for mod_id, mod_file_id in mod_and_mod_file_tuples
			]

			return await tqdm.gather(*tasks, file=sys.stdout)
