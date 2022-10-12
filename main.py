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
	mod_files: list[ModFile] = client.get_mod_files(mod.game_id, mod.id)
	pprint(mod_files)


if __name__ == '__main__':
	main()
