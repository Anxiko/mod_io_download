import pydantic
from pydantic import Field, StrictStr

from api_client.models.game import Game
from api_client.models.mod import Mod
from api_client.models.mod_file import ModFile


class StorageMod(pydantic.BaseModel):
	downloaded_filename: StrictStr
	downloaded_hash: StrictStr
	mod_data: Mod
	mod_file_data: ModFile


class StorageGame(pydantic.BaseModel):
	data: Game
	mods: dict[StrictStr, StorageMod]


class Storage(pydantic.BaseModel):
	games: dict[StrictStr, StorageGame] = Field(default_factory=dict)
