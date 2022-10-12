import asyncio
import logging
import os
from functools import partial
from logging import Logger
from pathlib import Path

from api_client.client import ApiClient
from api_client.models.game import Game
from api_client.models.mod import Mod, ModPlatform
from api_client.models.mod_file import ModFile
from api_client.models.platform import TargetPlatform
from config import Config
from downloader_client.client import DownloaderClient
from downloader_client.task import DownloadResult, DownloadTask
from logger import get_logger
from logger.logger import logger_set_up
from storage.manager import ModStorageManager

DOWNLOADS_PATH: Path = Path('./downloads')
BONELAB_NAME_ID: str = 'bonelab'
PLATFORM: TargetPlatform = TargetPlatform.WINDOWS

logger: Logger = get_logger(__name__)


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


def download_mods(download_tasks: list[DownloadTask]) -> list[DownloadResult]:
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


def split_download_results(
		download_results: list[DownloadResult]
) -> tuple[list[DownloadResult], list[DownloadResult]]:
	downloads_ok: list[DownloadResult] = []
	downloads_error: list[DownloadResult] = []

	for download_result in download_results:
		if download_result.is_ok():
			downloads_ok.append(download_result)
		else:
			downloads_error.append(download_result)

	return downloads_ok, downloads_error


def main() -> None:
	logger.info("Starting...")
	config: Config = Config.from_file()
	client: ApiClient = ApiClient(
		api_url=config.api_url, api_key=config.api_key, oauth_key=config.oauth_token
	)

	bonelab_game: Game = get_game_by_name_id(client, BONELAB_NAME_ID)
	logger.debug(f"Got target game: {bonelab_game}")

	my_mods: list[Mod] = client.get_mod_subscriptions(
		game_id=bonelab_game.id, platform=TargetPlatform.WINDOWS
	)
	logger.info(f"Found {len(my_mods)} mod(s) subscriptions for {bonelab_game}")
	logger.debug(f"{my_mods=}")

	storage_manager: ModStorageManager = ModStorageManager.from_file()

	download_tasks: list[DownloadTask] = list(map(partial(to_download_task, client, bonelab_game), my_mods))
	logger.info(f"Generated {len(download_tasks)} download task(s)")
	logger.debug(f"{download_tasks=}")

	filtered_download_tasks: list[DownloadTask] = filter_necessary_downloads(storage_manager, download_tasks)
	logger.info(f"Filtered needed downloads to {len(filtered_download_tasks)}")
	logger.debug(f"{filtered_download_tasks=}")

	results: list[DownloadResult] = download_mods(filtered_download_tasks)
	logger.info(f"Generated {len(results)} result(s)")
	logger.debug(f"{results=}")

	results_ok, results_error = split_download_results(results)
	if results_ok:
		logger.info(f"{results_ok} download(s) OK")
	if results_error:
		logger.warning(f"{len(results_error)} download(s) failed")
		for result_error in results_error:
			logger.debug(result_error)

	logger.info(f"Updating storage manager with correct results")
	storage_manager.update_storage(results_ok)

	logger.info(f"Closing...")


if __name__ == '__main__':
	logger_set_up()
	main()
