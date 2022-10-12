import json
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass
class Config:
	_FILENAME: ClassVar[str] = "config.json"
	api_key: str
	api_url: str
	oauth_token: str

	@classmethod
	def from_file(cls) -> 'Config':
		with open(cls._FILENAME, encoding='utf8') as f:
			raw: dict[str, Any] = json.load(f)
			return cls(**raw)
