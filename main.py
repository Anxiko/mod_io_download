from pathlib import Path
from pprint import pprint

from api_client.client import ApiClient
from api_client.models import Game, Mod, ModFile, ModPlatform, TargetPlatform
from config import Config


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


DOWNLOADS_PATH: Path = Path('./downloads')


def _download_mod_file(filename: str, mod_file: ModFile, client: ApiClient) -> None:
	with open(DOWNLOADS_PATH / filename, mode='wb') as f:
		client.download_mod_file(mod_file, f)


def main() -> None:
	config: Config = Config.from_file()
	client: ApiClient = ApiClient(api_url=config.api_url, api_key=config.api_key, oauth_key=config.oauth_token)
	"""
	games: list[Game] = client.get_games()
	bonelab: Game = _get_game_by_name(games, 'bonelab')

	bonelab_mods: list[Mod] = client.get_game_mods(bonelab.id)
	pprint(bonelab_mods)
	"""

	my_mods: list[Mod] = client.get_mod_subscriptions()
	mod_with_platform: tuple[Mod, ModPlatform] = _get_mod_with_windows_download(my_mods)
	mod: Mod
	mod_platform: ModPlatform
	mod, mod_platform = mod_with_platform
	game: Game = client.get_game_by_id(mod.game_id)
	mod_files: list[ModFile] = client.get_mod_files(mod.game_id, mod.id)

	latest_windows_mod_file: ModFile = _get_latest_windows_mod_file(mod_files)

	print(latest_windows_mod_file)
	filename: str = _generate_filename(game, mod, latest_windows_mod_file, TargetPlatform.WINDOWS)
	_download_mod_file(filename, latest_windows_mod_file, client)


if __name__ == '__main__':
	main()
