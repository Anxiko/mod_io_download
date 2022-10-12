import asyncio
import logging
import os
from functools import partial
from logging import Logger
from pathlib import Path
from pprint import pprint

from api_client.client import ApiClient
from api_client.models.game import Game
from api_client.models.mod import Mod, ModPlatform
from api_client.models.mod_file import ModFile
from api_client.models.platform import TargetPlatform
from config import Config
from downloader_client.client import DownloaderClient
from downloader_client.task import DownloadResult, DownloadTask
from storage.manager import ModStorageManager

DOWNLOADS_PATH: Path = Path('./downloads')
BONELAB_NAME_ID: str = 'bonelab'
PLATFORM: TargetPlatform = TargetPlatform.WINDOWS

logger: Logger = logging.getLogger(__name__)


def generate_filename(game: Game, mod: Mod, mod_file: ModFile, platform: TargetPlatform) -> str:
	name: str = '_'.join(filter(bool, [game.name_id, mod.name_id, mod_file.version, platform.value]))
	extension: str = ''.join(Path(mod_file.filename).suffixes)
	return f'{name}{extension}'


def to_download_task(client: ApiClient, game: Game, mod: Mod) -> DownloadTask:
	mod_platform: ModPlatform = mod.get_platform(PLATFORM)
	mod_file: ModFile = client.get_mod_file_by_id(
		game_id=game.id, mod_id=mod.id, mod_file_id=mod_platform.modfile_live
	)

	filename: str = generate_filename(game, mod, mod_file, PLATFORM)
	dir_path: Path = DOWNLOADS_PATH / game.name_id / mod.name_id
	os.makedirs(dir_path, exist_ok=True)

	return DownloadTask(
		download_file_path=dir_path / filename,
		download_url=str(mod_file.download.binary_url),
		game=game,
		mod=mod,
		mod_file=mod_file
	)


def filter_necessary_downloads(
		storage_manager: ModStorageManager, download_tasks: list[DownloadTask]
) -> list[DownloadTask]:
	return list(filter(
		storage_manager.needs_download,
		download_tasks
	))


def download_mods(client: ApiClient, game: Game, mods: list[Mod]) -> list[DownloadResult]:
	DOWNLOADS_PATH.mkdir(exist_ok=True)

	download_tasks: list[DownloadTask] = list(map(
		partial(to_download_task, client, game),
		mods
	))

	downloader_client: DownloaderClient = DownloaderClient(download_tasks)
	results: list[DownloadResult] = asyncio.run(downloader_client.download())
	return results


def get_game_by_name_id(client: ApiClient, name_id: str) -> Game:
	games: list[Game] = client.get_games(name_id=name_id)
	if len(games) == 0:
		raise ValueError(f"Found no games for {name_id=!r}")
	if len(games) > 1:
		raise ValueError(f"Found too many games ({len(games)}) for {name_id=!r}")
	return games[0]


def updated_storage_with_results(storage: ModStorageManager, download_results: list[DownloadResult]) -> None:
	storage.update_storage(
		filter(DownloadResult.is_ok, download_results)
	)


def main() -> None:
	config: Config = Config.from_file()
	client: ApiClient = ApiClient(
		api_url=config.api_url, api_key=config.api_key, oauth_key=config.oauth_token
	)

	bonelab_game: Game = get_game_by_name_id(client, BONELAB_NAME_ID)

	my_mods: list[Mod] = client.get_mod_subscriptions(
		game_id=bonelab_game.id, platform=TargetPlatform.WINDOWS
	)

	storage_manager: ModStorageManager = ModStorageManager.from_file()

	download_tasks: list[DownloadTask] = list(map(partial(to_download_task, client, bonelab_game), my_mods))
	filtered_download_tasks: list[DownloadTask] = filter_necessary_downloads(storage_manager, download_tasks)

	pprint(filtered_download_tasks)
	results: list[DownloadResult] = download_mods(client, bonelab_game, my_mods)
	updated_storage_with_results(storage_manager, results)


if __name__ == '__main__':
	main()
