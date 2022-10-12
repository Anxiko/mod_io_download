import hashlib
from functools import partial
from pathlib import Path
from typing import Callable, TypeVar

from api_client.models.game import Game
from downloader_client.task import DownloadTask
from .models import Storage, StorageGame, StorageMod

K = TypeVar('K')
V = TypeVar('V')


class ModStorageManager:
	_FILE_PATH: Path = Path('./storage.json')
	_HASH_CHUNK_SIZE: int = 4096

	_storage: Storage
	_download_dir: Path

	def __init__(self, storage: Storage, download_dir: Path):
		self._storage = storage
		self._download_dir = download_dir
		self._validate()
		self._save_to_file()

	@classmethod
	def from_file(cls, download_dir: Path) -> 'ModStorageManager':
		if cls._FILE_PATH.exists():
			storage: Storage = Storage.parse_file(cls._FILE_PATH)
			return cls(storage, download_dir)
		return cls(Storage(), download_dir)

	def _save_to_file(self) -> None:
		as_json: str = self._storage.json()
		with open(self._FILE_PATH, mode='w', encoding='utf8') as f:
			f.write(as_json)

	def _map_filter_game_mod(
			self, _game: StorageGame, game_dir: Path, mod_name: str, mod_data: StorageMod
	) -> tuple[str, StorageMod] | None:
		mod_dir: Path = game_dir / mod_name
		if not mod_dir.is_dir():
			return None
		mod_file: Path = mod_dir / mod_data.downloaded_filename
		if not mod_file.is_file():
			return None

		calculated_hash: str = self._hash_md5(mod_file)
		if calculated_hash != mod_data.downloaded_hash:
			return None

		return mod_name, mod_data

	def _map_filter_game(self, game_name: str, game_data: StorageGame) -> tuple[str, StorageGame] | None:
		game_dir: Path = self._download_dir / game_name
		if not game_dir.is_dir():
			return None
		return (
			game_name,
			StorageGame(
				game_data.data,
				self._apply_map_filter(game_data.mods, partial(self._map_filter_game_mod, game_data, game_dir))
			)
		)

	@staticmethod
	def _apply_map_filter(d: dict[K, V], map_filter: Callable[[K, V], tuple[K, V] | None]) -> dict[K, V]:
		return dict(filter(
			lambda x: x is not None,
			map(
				lambda kv: map_filter(*kv),
				d.items()
			)
		))

	@classmethod
	def _hash_md5(cls, file_path: Path) -> str:
		hasher = hashlib.md5()
		with open(file_path, mode='rb') as f:
			for chunk in iter(lambda: f.read(cls._HASH_CHUNK_SIZE), b''):
				hasher.update(chunk)
		return hasher.hexdigest()

	def _validate(self) -> None:
		validated_games: dict[str, StorageGame] = self._apply_map_filter(self._storage.games, self._map_filter_game)
		self._storage = Storage(games=validated_games)

	def _get_mod(self, game_name: str, mod_name: str) -> StorageMod | None:
		try:
			return self._storage.games[game_name].mods[mod_name]
		except KeyError:
			return None

	def needs_download(self, download_task: DownloadTask) -> bool:
		mod: StorageMod | None = self._get_mod(download_task.game.name, download_task.mod.name)
		if mod is None:
			return True
		return mod.mod_file_data.id != download_task.mod_file.id
