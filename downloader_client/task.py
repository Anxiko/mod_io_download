from dataclasses import dataclass
from pathlib import Path


@dataclass
class DownloadTask:
	download_file_path: Path
	download_url: str


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
