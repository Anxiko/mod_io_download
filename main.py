from pprint import pprint

from api_client.client import ApiClient
from api_client.response import Game, Mod
from config import Config


def _get_game_by_name(games: list[Game], name: str) -> Game:
	return next(filter(Game.filter_by_name(name), games))


def main() -> None:
	config: Config = Config.from_file()
	client: ApiClient = ApiClient(api_url=config.api_url, api_key=config.api_key, oauth_key=config.oauth_token)

	games: list[Game] = client.get_games()
	bonelab: Game = _get_game_by_name(games, 'bonelab')

	bonelab_mods: list[Mod] = client.get_game_mods(bonelab.id)
	pprint(bonelab_mods)

	my_mods: list[Mod] = client.get_mod_subscriptions()
	pprint(my_mods)


if __name__ == '__main__':
	main()
