import logging
import logging
import sys
from string import Template
from threading import Lock
from types import TracebackType
from typing import Any, Awaitable, Optional, Type, TypeVar
from urllib.parse import urljoin

import httpx
import pydantic
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
	_httpx_client: httpx.AsyncClient | None
	_enter_count: int
	_lock: Lock

	_GET_MOD_FILE_ENDPOINT: Template = Template('games/${game_id}/mods/${mod_id}/files/${mod_file_id}')
	_FILE_MAX_SIZE: int = 500 * (1024 ** 2)  # 500MiB

	def __init__(
			self, api_key: str, oauth_key: str, api_url: str
	):
		self._api_key = api_key
		self._oauth_key = oauth_key
		self._api_url = api_url
		self._httpx_client = None
		self._enter_count = 0
		self._lock = Lock()

	async def __aenter__(self) -> 'ApiClient':
		with self._lock:
			if self._enter_count == 0:
				if self._httpx_client is not None:
					raise ApiClientException(
						f"Count was {self._enter_count=}, but client was {self._httpx_client=}"
					)
				self._httpx_client = await httpx.AsyncClient().__aenter__()
			self._enter_count += 1
			return self

	async def __aexit__(self, exc_type: Type[BaseException], exc_val: BaseException, exc_tb: TracebackType) -> None:
		with self._lock:
			if self._enter_count <= 0:
				raise ApiClientException(
					f"Attempted to exit, but count was {self._enter_count=}"
				)
			self._enter_count -= 1
			if self._enter_count == 0:
				await self._httpx_client.__aexit__(exc_type, exc_val, exc_tb)
				self._httpx_client = None

	def _form_url(self, endpoint: str | Template, **kwargs) -> str:
		if isinstance(endpoint, Template):
			endpoint = endpoint.substitute(kwargs)
		elif kwargs:
			raise TypeError("Can't substitute from str endpoint")
		return urljoin(self._api_url, endpoint)

	async def _run_request(self, request: httpx.Request, response_type: Type[ResponseType]) -> ResponseType:
		async with self:
			response: httpx.Response = await self._httpx_client.send(request)
			response.raise_for_status()

			return response_type.parse_obj(response.json())

	@staticmethod
	def _set_param(request: httpx.Request, key: str, value: Any) -> None:
		request.url = request.url.copy_set_param(key, value)

	@classmethod
	def _add_offset(cls, request: httpx.Request, offset: int = 0) -> None:
		cls._set_param(request, '_offset', offset)

	def _add_api_key_authorization(self, request: httpx.Request) -> None:
		self._set_param(request, 'api_key', self._api_key)

	def _add_oauth_authorization(self, request: httpx.Request) -> None:
		request.headers['Authorization'] = f'Bearer {self._oauth_key}'

	@staticmethod
	def _add_platform(request: httpx.Request, platform: TargetPlatform) -> None:
		request.headers['X-Modio-Platform'] = platform.value

	async def _run_paginated_request(
			self, request: httpx.Request, response_type: Type[InnerResponseType]
	) -> list[InnerResponseType]:
		async with self:
			offset: int = 0
			rv: list[InnerResponseType] = []
			while offset is not None:
				self._add_offset(request, offset)
				paginated_response: PaginatedResponse[response_type] = await self._run_request(
					request, PaginatedResponse[response_type]
				)
				rv.extend(paginated_response.data)
				offset = paginated_response.next_offset()
			return rv

	async def get_games(self, name_id: Optional[str] = None) -> list[Game]:
		logger.info(f"Getting all games, {name_id=}")
		request: httpx.Request = httpx.Request('GET', self._form_url('games'))
		if name_id is not None:
			self._set_param(request, 'name_id', name_id)
		self._add_api_key_authorization(request)
		return await self._run_paginated_request(request, Game)

	async def get_mod_subscriptions(
			self, game_id: Optional[int] = None, platform: TargetPlatform = None
	) -> list[Mod]:
		logger.info(f"Getting mod subscriptions, {game_id=}, {platform=}")
		request: httpx.Request = httpx.Request('GET', self._form_url('me/subscribed'))
		if game_id is not None:
			self._set_param(request, 'game_id', game_id)

		if platform:
			self._add_platform(request, platform)

		self._add_oauth_authorization(request)
		return await self._run_paginated_request(request, Mod)

	async def get_mod_file_by_id(self, game_id: int, mod_id: int, mod_file_id: int) -> ModFile:
		logger.info(f"Getting mod file for {game_id=}, {mod_id=}, {mod_file_id=}")
		request: httpx.Request = httpx.Request(
			'GET',
			self._form_url(
				self._GET_MOD_FILE_ENDPOINT, game_id=game_id, mod_id=mod_id, mod_file_id=mod_file_id
			)
		)
		self._add_api_key_authorization(request)
		return await self._run_request(request, ModFile)

	async def get_mod_files_concurrently(
			self, game_id: int, mod_and_mod_file_tuples: list[tuple[int, int]]
	) -> list[ModFile]:
		async with self:
			tasks: list[Awaitable[ModFile]] = [
				self.get_mod_file_by_id(game_id, mod_id, mod_file_id)
				for mod_id, mod_file_id in mod_and_mod_file_tuples
			]

			return await tqdm.gather(*tasks, file=sys.stdout)
