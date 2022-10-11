import json
from dataclasses import dataclass
from pprint import pprint
from typing import Any, ClassVar

from api_client.client import ApiClient
from api_client.response import Game


@dataclass
class Config:
	_FILENAME: ClassVar[str] = "config.json"
	api_key: str
	api_url: str

	@classmethod
	def from_file(cls) -> 'Config':
		with open(cls._FILENAME, encoding='utf8') as f:
			raw: dict[str, Any] = json.load(f)
			return cls(**raw)


def main() -> None:
	config: Config = Config.from_file()
	client: ApiClient = ApiClient(api_url=config.api_url, api_key=config.api_key)

	games: list[Game] = client.get_games()
	pprint(games)


if __name__ == '__main__':
	main()
