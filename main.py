import asyncio
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
from installer.installer import ModInstaller
from installer.task import InstallationResult, InstallationTask
from logger import get_logger
from logger.logger import logger_set_up
from storage.manager import ModStorageManager
from utils.containers import binary_partition
from utils.files import nuke_path

DOWNLOADS_PATH: Path = Path('./downloads')
EXTRACTIONS_PATH: Path = Path('./extractions')
CONFIG_FILE: Path = Path('./config.json')
STORAGE_FILE: Path = Path('./storage.json')

BONELAB_NAME_ID: str = 'bonelab'
PLATFORM: TargetPlatform = TargetPlatform.WINDOWS

logger: Logger = get_logger(__name__)


def generate_filename(game: Game, mod: Mod, mod_file: ModFile, platform: TargetPlatform) -> str:
	name: str = '_'.join(filter(bool, [game.name_id, mod.name_id, mod_file.version, platform.value]))
	extension: str = ''.join(Path(mod_file.filename).suffixes)
	return f'{name}{extension}'


async def to_download_task(client: ApiClient, game: Game, mod: Mod) -> DownloadTask:
	mod_platform: ModPlatform = mod.get_platform(PLATFORM)
	mod_file: ModFile = await client.get_mod_file_by_id(
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


def download_mods(download_tasks: list[DownloadTask]) -> list[DownloadResult]:
	downloader_client: DownloaderClient = DownloaderClient(download_tasks)
	results: list[DownloadResult] = asyncio.run(downloader_client.download())
	return results


async def get_game_by_name_id(client: ApiClient, name_id: str) -> Game:
	games: list[Game] = await client.get_games(name_id=name_id)
	if len(games) == 0:
		raise ValueError(f"Found no games for {name_id=!r}")
	if len(games) > 1:
		raise ValueError(f"Found too many games ({len(games)}) for {name_id=!r}")
	return games[0]


def filter_need_download_mods(game: Game, mods: list[Mod], storage: ModStorageManager) -> list[Mod]:
	def mod_need_download(mod: Mod) -> bool:
		latest_mod_file_id: int = mod.get_platform(PLATFORM).modfile_live
		return storage.needs_download(game.name_id, mod.name_id, latest_mod_file_id)

	return list(filter(
		mod_need_download,
		mods
	))


def install_downloaded_mods(
		installer: ModInstaller, installation_tasks: list[InstallationTask]
) -> list[InstallationResult]:
	return list(map(installer.extract_and_install, installation_tasks))


def uninstalled_unsubscribed_mods(
		manager: ModStorageManager, game: Game, subscribed_mods: list[Mod]
) -> set[str]:
	return manager.remove_unsubscribed_mods(game.name_id, subscribed_mods)


async def main() -> None:
	logger.info("Starting...")
	config: Config = Config.from_file()
	client: ApiClient = ApiClient(
		api_url=config.api_url, api_key=config.api_key, oauth_key=config.oauth_token
	)

	appdata: str = os.getenv('APPDATA')
	appdata_path: Path = Path(appdata)
	mods_folder: Path = appdata_path.parent / 'LocalLow' / 'Stress Level Zero' / 'BONELAB' / 'Mods'
	if not mods_folder.is_dir():
		error_msg: str = f"Mods folder does not exist: {mods_folder}"
		raise Exception(error_msg)
	logger.info(f"Resolved mods folder to: {mods_folder}")

	bonelab_game: Game = await get_game_by_name_id(client, BONELAB_NAME_ID)
	logger.debug(f"Got target game: {bonelab_game}")

	my_mods: list[Mod] = await client.get_mod_subscriptions(
		game_id=bonelab_game.id, platform=TargetPlatform.WINDOWS
	)
	logger.info(f"Found {len(my_mods)} mod(s) subscriptions for {bonelab_game}")
	logger.debug(f"{my_mods=}")

	logger.info("Verifying managed mods...")
	storage_manager: ModStorageManager = ModStorageManager.from_file()
	storage_manager.validate()
	logger.info(f"Verified managed mods integrity")

	all_mod_files: list[ModFile] = await client.get_mod_files_concurrently(
		bonelab_game.id, [(mod.id, mod.get_platform(PLATFORM).modfile_live) for mod in my_mods]
	)
	logger.debug(all_mod_files)

	mods_need_download: list[Mod] = filter_need_download_mods(bonelab_game, my_mods, storage_manager)
	logger.info(f"{len(mods_need_download)} mod(s) to download")
	logger.debug(f"Mods to download: {mods_need_download}")

	if len(mods_need_download) > 0:
		download_tasks: list[DownloadTask] = list(
			map(partial(to_download_task, client, bonelab_game), mods_need_download))
		logger.info(f"Generated {len(download_tasks)} download task(s)")
		logger.debug(f"{download_tasks=}")

		download_results: list[DownloadResult] = download_mods(download_tasks)
		logger.info(f"Generated {len(download_results)} result(s)")
		logger.debug(f"{download_results=}")

		download_results_ok: list[DownloadResult]
		download_results_error: list[DownloadResult]

		download_results_ok, download_results_error = binary_partition(download_results, DownloadResult.is_ok)
		if download_results_ok:
			logger.info(f"{len(download_results_ok)} download(s) OK")
		if download_results_error:
			logger.warning(f"{len(download_results_error)} download(s) failed")
			logger.debug(f"Failed to download: {download_results_error}")

		logger.info(f"Updating storage manager with downloaded mods")
		storage_manager.update_downloaded_mods(download_results_ok)

	installation_tasks: list[InstallationTask] = storage_manager.generate_mod_install_tasks(
		bonelab_game, my_mods, PLATFORM
	)

	logger.info(f"{len(installation_tasks)} mod(s) to install")
	logger.debug(f"Mods to install: {installation_tasks}")

	if len(installation_tasks) > 0:
		installer: ModInstaller = ModInstaller(EXTRACTIONS_PATH, mods_folder)
		installation_results: list[InstallationResult] = install_downloaded_mods(installer, installation_tasks)

		installed_ok: list[InstallationResult]
		installed_error: list[InstallationResult]

		installed_ok, installed_error = binary_partition(installation_results, InstallationResult.is_ok)

		if installed_ok:
			logger.info(f"Installed {len(installed_ok)} mod(s)")
			logger.debug(f"Installed mods are: {installed_ok}")

		if installed_error:
			logger.warning(f"Failed to install {len(installed_error)} mod(s)")
			logger.debug(f"Failed to install mods are: {installed_error}")

		logger.info("Updating store manager with installed mods")
		storage_manager.update_installed_mods(installed_ok)

	logger.info("Uninstalling managed mods no longer subscribed to")
	uninstalled_mods: set[str] = uninstalled_unsubscribed_mods(storage_manager, bonelab_game, my_mods)
	logger.info(f"Uninstalled {len(uninstalled_mods)} mod(s)")
	logger.debug(f"Uninstalled mods are: {uninstalled_mods}")

	logger.info(f"Removing extractions directory: {EXTRACTIONS_PATH}")
	nuke_path(EXTRACTIONS_PATH)

	logger.info(f"Closing...")


if __name__ == '__main__':
	logger_set_up()
	asyncio.run(main())
