import logging
from dataclasses import dataclass
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

DOWNLOADS_PATH: Path = Path('./downloads')
BONELAB_NAME_ID: str = 'bonelab'
PLATFORM: TargetPlatform = TargetPlatform.WINDOWS

logger: Logger = logging.getLogger(__name__)


@dataclass
class DownloadTask:
	download_file_path: Path
	download_url: str


def _get_game_by_name(games: list[Game], name: str) -> Game:
	return next(filter(Game.filter_by_name(name), games))


def _get_mod_with_windows_download(mods: list[Mod]) -> tuple[Mod, ModPlatform]:
	return next(filter(
		lambda x: x is not None,
		map(
			lambda x: x.with_platform_download(TargetPlatform.WINDOWS),
			mods
		)
	))


def _get_latest_windows_mod_file(mod_files: list[ModFile]) -> ModFile:
	sorted_windows_mod_files: list[ModFile] = sorted(
		filter(
			ModFile.filter_by_platform_support(TargetPlatform.WINDOWS),
			mod_files
		),
		key=ModFile.sort_by_version_key,
		reverse=True
	)
	return sorted_windows_mod_files[0]


def _generate_filename(game: Game, mod: Mod, mod_file: ModFile, platform: TargetPlatform) -> str:
	name: str = '_'.join(filter(bool, [game.name_id, mod.name_id, mod_file.version, platform.value]))
	extension: str = ''.join(Path(mod_file.filename).suffixes)
	return f'{name}{extension}'


def _download_mod_file(filename: str, mod_file: ModFile, client: ApiClient) -> None:
	with open(DOWNLOADS_PATH / filename, mode='wb') as f:
		client.download_mod_file(mod_file, f)


def _to_download_task(client: ApiClient, game: Game, mod: Mod) -> DownloadTask:
	mod_platform: ModPlatform = mod.get_platform(PLATFORM)
	mod_file: ModFile = client.get_mod_file_by_id(
		game_id=game.id, mod_id=mod.id, mod_file_id=mod_platform.modfile_live
	)

	filename: str = _generate_filename(game, mod, mod_file, PLATFORM)
	file_path: Path = DOWNLOADS_PATH / filename

	return DownloadTask(
		download_file_path=file_path,
		download_url=str(mod_file.download.binary_url)
	)


def _download_mods(client: ApiClient, game: Game, mods: list[Mod]) -> None:
	download_tasks: list[DownloadTask] = list(map(
		partial(_to_download_task, client, game),
		mods
	))
	pprint(download_tasks)


def _get_game_by_name_id(client: ApiClient, name_id: str) -> Game:
	games: list[Game] = client.get_games(name_id=name_id)
	if len(games) == 0:
		raise ValueError(f"Found no games for {name_id=!r}")
	if len(games) > 1:
		raise ValueError(f"Found too many games ({len(games)}) for {name_id=!r}")
	return games[0]


def main() -> None:
	config: Config = Config.from_file()
	client: ApiClient = ApiClient(
		api_url=config.api_url, api_key=config.api_key, oauth_key=config.oauth_token
	)

	bonelab_game: Game = _get_game_by_name_id(client, BONELAB_NAME_ID)

	my_mods: list[Mod] = client.get_mod_subscriptions(
		game_id=bonelab_game.id, platform=TargetPlatform.WINDOWS
	)

	_download_mods(client, bonelab_game, my_mods)


if __name__ == '__main__':
	main()
