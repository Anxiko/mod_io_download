import enum
from dataclasses import dataclass
from pathlib import Path

from api_client.models.game import Game
from api_client.models.mod import Mod
from api_client.models.mod_file import ModFile


@dataclass
class InstallationTask:
	downloaded_path: Path
	game: Game
	mod: Mod
	mod_file: ModFile


class InstallationResultFailReason(enum.Enum):
	NO_PALLET_FOUND = enum.auto()
	NO_FILTERED_PALLET_FOUND = enum.auto()
	TOO_MANY_FILTERED_PALLETS_FOUND = enum.auto()


@dataclass
class InstallationResultOk:
	installed_paths: list[Path]


@dataclass
class InstallationResultFail:
	reason: InstallationResultFailReason


@dataclass
class InstallationResult:
	task: InstallationTask
	result: InstallationResultOk | InstallationResultFail

	@classmethod
	def create_ok(cls, installation_task: InstallationTask, installed_paths: list[Path]) -> 'InstallationResult':
		return cls(installation_task, InstallationResultOk(installed_paths))

	@classmethod
	def create_error(
			cls, installation_task: InstallationTask, failure_reason: InstallationResultFailReason
	) -> 'InstallationResult':
		return cls(installation_task, InstallationResultFail(failure_reason))

	def is_ok(self) -> bool:
		return isinstance(self.result, InstallationResultOk)
