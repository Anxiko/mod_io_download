from pathlib import Path

import pydantic
from pydantic import Field, StrictInt


class StoredModFile(pydantic.BaseModel):
	mod_file_id: StrictInt
	file_path: str
	file_hash: str

	def get_as_path(self) -> Path:
		return Path(self.file_path)


class Storage(pydantic.BaseModel):
	games: dict[str, dict[str, StoredModFile]] = Field(default_factory=dict)
