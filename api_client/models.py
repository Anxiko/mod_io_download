from enum import Enum
from typing import Callable

from pydantic import BaseModel, Field, HttpUrl, StrictInt, StrictStr, validator


class VirusStatus(Enum):
	NOT_SCANNED = 0
	SCAN_COMPLETE = 1
	IN_PROGRESS = 2
	TOO_LARGE = 3
	FILE_NOT_FOUND = 4
	SCAN_ERROR = 5


class Download(BaseModel):
	binary_url: HttpUrl
	date_expires: int


class ModFile(BaseModel):
	id: StrictInt
	mod_id: StrictInt
	virus_status: VirusStatus
	virus_positive: bool
	download: Download


class ModPlatform(BaseModel):
	platform: StrictStr
	modfile_live: StrictInt


class Mod(BaseModel):
	id: StrictInt
	game_id: StrictInt
	name: StrictStr
	name_id: StrictStr
	modfile: ModFile
	platforms: list[ModPlatform]


class Game(BaseModel):
	id: StrictInt
	name: StrictStr
	name_id: StrictStr

	@staticmethod
	def filter_by_name(name: str) -> Callable[['Game'], bool]:
		def f(game: 'Game') -> bool:
			return game.name_id == name

		return f
