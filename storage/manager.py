import hashlib
from os import PathLike
from pathlib import Path
from typing import Iterable, TypeVar

from api_client.models.game import Game
from api_client.models.mod import Mod
from api_client.models.platform import TargetPlatform
from downloader_client.task import DownloadResult
from installer.task import InstallationResult, InstallationTask
from .models import DownloadedManagedMod, InstalledManagedMod, ManagedMod, Storage

K = TypeVar('K')
V = TypeVar('V')


class StorageException(Exception):
	pass


class StorageUpdateException(StorageException):
	@classmethod
	def for_download_update(cls, download_result: DownloadResult) -> 'StorageUpdateException':
		return cls(f"Can't update the storage state with a failed download: {download_result}")

	@classmethod
	def for_installation_update(cls, installation_result: InstallationResult) -> 'StorageUpdateException':
		return cls(f"Can't update the storage state with a failed installation: {installation_result}")


class ModStorageManager:
	_FILE_PATH: Path = Path('./storage.json')
	_HASH_CHUNK_SIZE: int = 4096

	_storage: Storage
	_download_dir: Path

	def __init__(self, storage: Storage):
		self._storage = storage
		self._validate()
		self._save_to_file()

	@classmethod
	def from_file(cls) -> 'ModStorageManager':
		if cls._FILE_PATH.exists():
			storage: Storage = Storage.parse_file(cls._FILE_PATH)
			return cls(storage)
		return cls(Storage())

	def needs_download(self, game_name_id: str, mod_name_id: str, mod_file_id: int) -> bool:
		mod: ManagedMod | None = self._storage.read_managed_mod(game_name_id, mod_name_id)
		if mod is None:
			return True
		return not mod.has_mod_file_installed(mod_file_id) and not mod.has_mod_file_downloaded(mod_file_id)

	def update_downloaded_mods(self, download_results: Iterable[DownloadResult]) -> None:
		for download_result in download_results:
			if not download_result.is_ok():
				raise StorageUpdateException.for_download_update(download_result)

			game_name_id: str = download_result.task.game.name_id
			mod_name_id: str = download_result.task.mod.name_id

			mod_file_id: int = download_result.task.mod_file.id
			file_path: Path = download_result.task.download_file_path
			file_hash: str = self._hash_md5(download_result.task.download_file_path)

			downloaded_managed_mod: DownloadedManagedMod = DownloadedManagedMod(
				mod_file_id=mod_file_id,
				file_path=file_path,
				file_hash=file_hash
			)

			maybe_managed_mod: ManagedMod | None = self._storage.read_managed_mod(game_name_id, mod_name_id)
			if maybe_managed_mod is None:
				maybe_managed_mod = ManagedMod(downloaded_mod=downloaded_managed_mod)
			else:
				maybe_managed_mod.downloaded_mod = downloaded_managed_mod

			self._storage.write_managed_mod(game_name_id, mod_name_id, maybe_managed_mod)
		self._save_to_file()

	def generate_mod_install_tasks(
			self, game: Game, mods: list[Mod], platform: TargetPlatform
	) -> list[InstallationTask]:
		try:
			managed_mods_dict: dict[str, ManagedMod] = self._storage.games[game.name_id]
		except KeyError:
			return []

		installation_tasks: list[InstallationTask] = []
		mod: Mod
		for mod in mods:
			mod_file_id: int = mod.get_platform(platform).modfile_live

			try:
				managed_mod: ManagedMod = managed_mods_dict[mod.name_id]
			except KeyError:
				continue

			if managed_mod.has_mod_file_downloaded(mod_file_id) and not managed_mod.has_mod_file_installed(mod_file_id):
				installation_task: InstallationTask = InstallationTask(
					downloaded_path=managed_mod.downloaded_mod.file_path,
					game_name_id=game.name_id,
					mod_name_id=mod.name_id,
					mod_file_id=mod_file_id
				)
				installation_tasks.append(installation_task)

		return installation_tasks

	def needs_installation(self, game_name_id: str, mod_name_id: str, mod_file_id: int) -> bool:
		mod: ManagedMod | None = self._storage.read_managed_mod(game_name_id, mod_name_id)
		if mod is None:
			return False

		return not mod.has_mod_file_installed(mod_file_id)

	def update_installed_mods(self, installation_results: Iterable[InstallationResult]) -> None:
		for installation_result in installation_results:
			if not installation_result.is_ok():
				raise StorageUpdateException.for_installation_update(installation_result)

			game_name_id: str = installation_result.task.game_name_id
			mod_name_id: str = installation_result.task.mod_name_id

			mod_file_id: int = installation_result.task.mod_file_id
			installed_paths: list[Path] = installation_result.result.installed_paths

			installed_managed_mod: InstalledManagedMod = InstalledManagedMod(
				mod_file_id=mod_file_id,
				installed_paths=installed_paths
			)

			maybe_managed_mod: ManagedMod | None = self._storage.read_managed_mod(game_name_id, mod_name_id)
			if maybe_managed_mod is None:
				raise ValueError(
					f"Attempted to update mod installation for {game_name_id}, {mod_name_id} that doesn't exist"
				)
			else:
				maybe_managed_mod.installed_mod = installed_managed_mod

			self._storage.write_managed_mod(game_name_id, mod_name_id, maybe_managed_mod)
		self._save_to_file()

	def _save_to_file(self) -> None:
		as_json: str = self._storage.json(indent='\t', ensure_ascii=False)
		with open(self._FILE_PATH, mode='w', encoding='utf8') as f:
			f.write(as_json)

	@classmethod
	def _hash_md5(cls, file_path: PathLike) -> str:
		hasher = hashlib.md5()
		with open(file_path, mode='rb') as f:
			for chunk in iter(lambda: f.read(cls._HASH_CHUNK_SIZE), b''):
				hasher.update(chunk)
		return hasher.hexdigest()

	@classmethod
	def _verify_downloaded_mod(cls, downloaded_mod: DownloadedManagedMod | None) -> DownloadedManagedMod | None:
		if downloaded_mod is None:
			return None

		downloaded_file_path: Path = downloaded_mod.file_path
		if not downloaded_file_path.is_file():
			return None

		calculated_hash: str = cls._hash_md5(downloaded_file_path)
		if calculated_hash == downloaded_mod.file_hash:
			return downloaded_mod
		return None

	@staticmethod
	def _verify_installed_mod(installed_mod: InstalledManagedMod | None) -> InstalledManagedMod | None:
		if installed_mod is None:
			return None

		verified_installed_paths: list[Path] = list(filter(
			Path.is_dir,
			installed_mod.installed_paths
		))

		return InstalledManagedMod(
			mod_file_id=installed_mod.mod_file_id,
			installed_paths=verified_installed_paths
		)

	def _entry_is_valid(self, _game_name_id: str, _mod_name_id: str, stored_mod_file: ManagedMod) -> bool:
		verified_downloaded_mod: DownloadedManagedMod | None = self._verify_downloaded_mod(
			stored_mod_file.downloaded_mod
		)

		verified_installed_mod: InstalledManagedMod | None = self._verify_installed_mod(
			stored_mod_file.installed_mod
		)

		stored_mod_file.downloaded_mod = verified_downloaded_mod
		stored_mod_file.installed_mod = verified_installed_mod

		return stored_mod_file.contains_info()

	def _validate(self) -> None:
		validated_storage: Storage = Storage()

		for game_name_id, game_mods in self._storage.games.items():
			for mod_name_id, managed_mod in game_mods.items():
				if self._entry_is_valid(game_name_id, mod_name_id, managed_mod):
					validated_storage.write_managed_mod(game_name_id, mod_name_id, managed_mod)

		self._storage = validated_storage

	def _get_mod(self, game_name_id: str, mod_name_id: str) -> ManagedMod | None:
		try:
			return self._storage.games[game_name_id][mod_name_id]
		except KeyError:
			return None
