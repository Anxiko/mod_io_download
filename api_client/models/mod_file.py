from enum import Enum
from typing import Callable, Optional

from pydantic import BaseModel, HttpUrl, StrictInt, StrictStr

from .platform import TargetPlatform


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


class ModFilePlatform(BaseModel):
	platform: TargetPlatform
	status: ModFilePlatformStatus

	@classmethod
	def filter_by_platform(cls, platform: TargetPlatform) -> Callable[['ModFilePlatform'], bool]:
		def f(mod_file_platform: 'ModFilePlatform') -> bool:
			return mod_file_platform.platform == platform

		return f


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

	def has_platform_support(self, platform: TargetPlatform) -> bool:
		return any(filter(
			ModFilePlatform.filter_by_platform(platform),
			self.platforms
		))

	@classmethod
	def filter_by_platform_support(cls, platform: TargetPlatform) -> Callable[['ModFile'], bool]:
		def f(mod_file: 'ModFile') -> bool:
			return mod_file.has_platform_support(platform)

		return f

	def sort_by_version_key(self) -> str:
		if self.version is None:
			return ""
		return self.version
