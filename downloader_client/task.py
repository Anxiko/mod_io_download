from dataclasses import dataclass
from pathlib import Path

from api_client.models.game import Game
from api_client.models.mod import Mod
from api_client.models.mod_file import ModFile


@dataclass
class DownloadTask:
	download_file_path: Path
	download_url: str
	game: Game
	mod: Mod
	mod_file: ModFile


@dataclass
class DownloadResultOk:
	total_bytes: int


@dataclass
class DownloadResultError:
	reason: Exception


@dataclass
class DownloadResult:
	task: DownloadTask
	result: DownloadResultOk | DownloadResultError

	@classmethod
	def result_ok(cls, task: DownloadTask, total_bytes: int) -> 'DownloadResult':
		return cls(task, DownloadResultOk(total_bytes))

	@classmethod
	def result_error(cls, task: DownloadTask, reason: Exception) -> 'DownloadResult':
		return cls(task, DownloadResultError(reason))

	def is_ok(self) -> bool:
		return isinstance(self.result, DownloadResultOk)
