import asyncio
import datetime
import multiprocessing
import os
import sys
from functools import partial
from logging import Logger
from pathlib import Path

from api_client.client import ApiClient
from api_client.models.export import SubscriptionsExport, SubscriptionsForGame
from api_client.models.game import Game
from api_client.models.mod import ModWithModfile
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
EXPORTS_PATH: Path = Path("./exports")
IMPORTS_PATH: Path = Path("./imports")

BONELAB_NAME_ID: str = 'bonelab'
PLATFORM: TargetPlatform = TargetPlatform.WINDOWS

logger: Logger = get_logger(__name__)


def generate_filename(game: Game, mod: ModWithModfile, mod_file: ModFile, platform: TargetPlatform) -> str:
	name: str = '_'.join(filter(bool, [game.name_id, mod.name_id, mod_file.version, platform.value]))
	extension: str = ''.join(Path(mod_file.filename).suffixes)
	return f'{name}{extension}'


def _to_download_task(game, mod_and_mod_file: tuple[ModWithModfile, ModFile]) -> DownloadTask:
	mod, mod_file = mod_and_mod_file
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


async def generate_download_tasks(client: ApiClient, game: Game, mods: list[ModWithModfile]) -> list[DownloadTask]:
	mod_files: list[ModFile] = await client.get_mod_files_concurrently(
		game.id,
		[
			(mod.id, mod.get_platform(PLATFORM).modfile_live)
			for mod in mods
		]
	)

	return list(map(
		partial(_to_download_task, game),
		zip(mods, mod_files)
	))


async def download_mods(download_tasks: list[DownloadTask]) -> list[DownloadResult]:
	downloader_client: DownloaderClient = DownloaderClient(download_tasks)
	results: list[DownloadResult] = await downloader_client.download()
	return results


async def get_game_by_name_id(client: ApiClient, name_id: str) -> Game:
	games: list[Game] = await client.get_games(name_id=name_id)
	if len(games) == 0:
		raise ValueError(f"Found no games for {name_id=!r}")
	if len(games) > 1:
		raise ValueError(f"Found too many games ({len(games)}) for {name_id=!r}")
	return games[0]


def filter_need_download_mods(game: Game, mods: list[ModWithModfile], storage: ModStorageManager) -> list[ModWithModfile]:
	def mod_need_download(mod: ModWithModfile) -> bool:
		latest_mod_file_id: int = mod.get_platform(PLATFORM).modfile_live
		return storage.needs_download(game.name_id, mod.name_id, latest_mod_file_id)

	return list(filter(
		mod_need_download,
		mods
	))


def install_downloaded_mods(
	installer: ModInstaller, installation_tasks: list[InstallationTask]
) -> list[InstallationResult]:
	with multiprocessing.Pool() as pool:
		return pool.map(installer.extract_and_install, installation_tasks)


def uninstalled_unsubscribed_mods(
	manager: ModStorageManager, game: Game, subscribed_mods: list[ModWithModfile]
) -> set[str]:
	return manager.remove_unsubscribed_mods(game.name_id, subscribed_mods)


async def _sync(
	client: ApiClient, bonelab_game: Game, my_mods: list[ModWithModfile], available_mods: list[ModWithModfile], mods_folder: Path
) -> None:
	logger.info("Verifying managed mods...")
	storage_manager: ModStorageManager = ModStorageManager.from_file()
	storage_manager.validate()
	logger.info(f"Verified managed mods integrity")

	mods_need_download: list[ModWithModfile] = filter_need_download_mods(bonelab_game, available_mods, storage_manager)
	logger.info(f"{len(mods_need_download)} mod(s) to download")
	logger.debug(f"Mods to download: {mods_need_download}")

	if len(mods_need_download) > 0:
		download_tasks: list[DownloadTask] = await generate_download_tasks(client, bonelab_game, mods_need_download)
		logger.info(f"Generated {len(download_tasks)} download task(s)")
		logger.debug(f"{download_tasks=}")

		download_results: list[DownloadResult] = await download_mods(download_tasks)
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


def _usage(name: str) -> None:
	print(f"Usage:")
	print(f"\t{name} [sync]")
	print(f"\t{name} export")
	print(f"\t{name} import <subs.json>")


def _export(bonelab_game: Game, available_mods: list[ModWithModfile]) -> None:
	logger.info(f"Exporting mod subscriptions for {bonelab_game.name_id}")
	export_content: SubscriptionsExport = SubscriptionsExport(
		subscriptions={
			bonelab_game.name_id: SubscriptionsForGame(
				game=bonelab_game,
				mods=available_mods
			)
		}
	)
	timestamp: str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
	filename: str = f"subs_export_{timestamp}.json"
	file_path: Path = EXPORTS_PATH / filename
	file_path.parent.mkdir(parents=True, exist_ok=True)
	logger.info(f"Exporting subscriptions to {file_path}")
	with open(file_path, mode='w', encoding='utf8', newline='\n') as f:
		as_json: str = export_content.json(indent='\t', ensure_ascii=False)
		f.write(as_json)


async def _import(subs_file: str, client: ApiClient, bonelab_game: Game, my_mods: list[ModWithModfile]) -> None:
	subs_file: Path = Path(subs_file)
	logger.info(f"Importing subscriptions from {subs_file}")
	if not subs_file.is_file():
		print(f"{subs_file}: not a valid path")
		return

	subscriptions_export: SubscriptionsExport = SubscriptionsExport.parse_file(subs_file)
	bonelab_subscriptions: SubscriptionsForGame = subscriptions_export.subscriptions[bonelab_game.name_id]
	export_bonelab_mods: set[int] = {mod.id for mod in bonelab_subscriptions.mods}

	logger.info(f"Parsed {len(export_bonelab_mods)} subscriptions for {bonelab_game.name_id}")

	my_subbed_mod_id_set: set[int] = {mod.id for mod in my_mods}
	missing_sub_mod_ids: list[int] = list(export_bonelab_mods - my_subbed_mod_id_set)

	if len(missing_sub_mod_ids) > 0:
		logger.info(f"Adding {len(missing_sub_mod_ids)} new subscription(s) for {bonelab_game.name_id}")
		logger.debug(f"{missing_sub_mod_ids}")
		subbed_mods: list[ModWithModfile] = await client.sub_to_mods_concurrently(
			bonelab_game.id, missing_sub_mod_ids
		)
		logger.info(f"Added {len(subbed_mods)} new subscription(s) for {bonelab_game.name_id}")
		logger.debug(f"{subbed_mods}")
	else:
		logger.info("No new subscriptions, skipping...")


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

	my_mods: list[ModWithModfile] = await client.get_mod_subscriptions(
		game_id=bonelab_game.id, platform=TargetPlatform.WINDOWS
	)
	logger.info(f"Found {len(my_mods)} mod(s) subscriptions for {bonelab_game}")
	logger.debug(f"{my_mods=}")

	unavailable_mods: list[ModWithModfile]
	available_mods: list[ModWithModfile]
	available_mods, unavailable_mods = binary_partition(my_mods, ModWithModfile.is_available)

	if len(unavailable_mods) > 0:
		logger.warning(f"{len(unavailable_mods)} mod(s) unavailable")
		logger.debug(f"{unavailable_mods=}")

	args: list[str] = sys.argv[1:]
	name: str
	name, *args = sys.argv

	match args:
		case [] | ["sync"]:
			await _sync(
				client=client,
				bonelab_game=bonelab_game,
				my_mods=my_mods,
				available_mods=available_mods,
				mods_folder=mods_folder
			)
		case ["export"]:
			_export(bonelab_game, available_mods)
		case ["import", subs_file]:
			await _import(subs_file=subs_file, client=client, bonelab_game=bonelab_game, my_mods=my_mods)
		case [*_invalid_args]:
			_usage(name)

	logger.info(f"Closing...")


if __name__ == '__main__':
	logger_set_up()
	asyncio.run(main())
