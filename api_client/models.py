from enum import Enum
from typing import Callable, Optional

from pydantic import BaseModel, HttpUrl, StrictInt, StrictStr


class TargetPlatform(Enum):
	WINDOWS = 'windows'
	MAC = 'mac'
	LINUX = 'linux'
	ANDROID = 'android'
	IOS = 'ios'
	XBOX_ONE = 'xboxone'
	XBOX_SERIES_X = 'xboxseriesx'
	PS4 = 'ps4'
	PS5 = 'ps5'
	SWITCH = 'switch'
	OCULUS = 'oculus'


class ModFilePlatformStatus(Enum):
	PENDING = 0
	APPROVED = 1
	DENIED = 2


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


class ModPlatform(BaseModel):
	platform: TargetPlatform
	modfile_live: StrictInt

	@classmethod
	def filter_by_platform(cls, platform: TargetPlatform) -> Callable[['ModPlatform'], bool]:
		def f(mod_platform: 'ModPlatform') -> bool:
			return mod_platform.platform == platform

		return f


class ModFilePlatform(BaseModel):
	platform: TargetPlatform
	status: ModFilePlatformStatus


class ModFile(BaseModel):
	id: StrictInt
	mod_id: StrictInt
	virus_status: VirusStatus
	virus_positive: bool
	filesize: StrictInt
	filehash: dict
	filename: StrictStr
	version: Optional[StrictStr]
	download: Download
	platforms: list[ModFilePlatform]


class Mod(BaseModel):
	id: StrictInt
	game_id: StrictInt
	name: StrictStr
	name_id: StrictStr
	modfile: ModFile
	platforms: list[ModPlatform]

	def with_platform_download(self, platform: TargetPlatform) -> tuple['Mod', 'ModPlatform'] | None:
		try:
			mod_platform: ModPlatform = next(filter(
				ModPlatform.filter_by_platform(platform),
				self.platforms
			))
			return self, mod_platform
		except StopIteration:
			return None


class Game(BaseModel):
	id: StrictInt
	name: StrictStr
	name_id: StrictStr

	@staticmethod
	def filter_by_name(name: str) -> Callable[['Game'], bool]:
		def f(game: 'Game') -> bool:
			return game.name_id == name

		return f
