import hashlib
from os import PathLike
from pathlib import Path
from typing import Iterable, TypeVar

from downloader_client.task import DownloadResult, DownloadTask
from .models import Storage, StoredModFile

K = TypeVar('K')
V = TypeVar('V')


class StorageException(Exception):
	pass


class StorageUpdateException(StorageException):
	download_result: DownloadResult

	def __init__(self, download_result: DownloadResult):
		self.download_result = download_result
		super().__init__(f"Can't upload the storage state with a failed download: {self.download_result}")


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

	def _save_to_file(self) -> None:
		as_json: str = self._storage.json()
		with open(self._FILE_PATH, mode='w', encoding='utf8') as f:
			f.write(as_json)

	@classmethod
	def _hash_md5(cls, file_path: PathLike) -> str:
		hasher = hashlib.md5()
		with open(file_path, mode='rb') as f:
			for chunk in iter(lambda: f.read(cls._HASH_CHUNK_SIZE), b''):
				hasher.update(chunk)
		return hasher.hexdigest()

	def _entry_is_valid(self, _game_name_id: str, _mod_name_id: str, stored_mod_file: StoredModFile) -> bool:
		try:
			file_path: Path = Path(stored_mod_file.file_path)
		except Exception:
			return False

		if not file_path.is_file():
			return False

		calculated_hash: str = self._hash_md5(file_path)
		return stored_mod_file.file_hash == calculated_hash

	def _validate(self) -> None:
		validated_games: dict[str, dict[str, StoredModFile]] = {}

		for game_name_id, game_mods in self._storage.games.items():
			validated_game_mods: dict[str, StoredModFile] = validated_games.setdefault(game_name_id, {})
			for mod_name_id, stored_mod_file in game_mods.items():
				if self._entry_is_valid(game_name_id, mod_name_id, stored_mod_file):
					validated_game_mods[mod_name_id] = stored_mod_file

		self._storage = Storage(games=validated_games)

	def _get_mod(self, game_name_id: str, mod_name_id: str) -> StoredModFile | None:
		try:
			return self._storage.games[game_name_id][mod_name_id]
		except KeyError:
			return None

	def needs_download(self, download_task: DownloadTask) -> bool:
		mod: StoredModFile | None = self._get_mod(download_task.game.name_id, download_task.mod.name_id)
		if mod is None:
			return True
		return mod.mod_file_id != download_task.mod_file.id

	def update_storage(self, download_results: Iterable[DownloadResult]) -> None:
		for download_result in download_results:
			if not download_result.is_ok():
				raise StorageUpdateException(download_result)

			game_name_id: str = download_result.task.game.name_id
			mod_name_id: str = download_result.task.mod.name_id

			mod_file_id: int = download_result.task.mod_file.id
			file_path: str = str(download_result.task.download_file_path)
			file_hash: str = self._hash_md5(download_result.task.download_file_path)

			stored_mod_file: StoredModFile = StoredModFile(
				mod_file_id=mod_file_id,
				file_path=file_path,
				file_hash=file_hash
			)

			self._storage.games.setdefault(game_name_id, {})[mod_name_id] = stored_mod_file
		self._save_to_file()

	def list_mod_files(self, game_name_id: str) -> list[Path]:
		mods_dict: dict[str, StoredModFile]
		try:
			mods_dict = self._storage.games[game_name_id]
		except KeyError:
			return list()

		return list(map(
			StoredModFile.get_as_path,
			mods_dict.values()
		))

	def downloaded_mod_file_id(self, game_name_id: str, mod_name_id: str) -> int | None:
		maybe_stored_mod_file: StoredModFile | None = self._get_mod(game_name_id, mod_name_id)
		return maybe_stored_mod_file.mod_file_id if maybe_stored_mod_file is not None else None
