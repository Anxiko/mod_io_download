from pathlib import Path

import pydantic
from pydantic import Field, StrictInt, StrictStr


class DownloadedManagedMod(pydantic.BaseModel):
	mod_file_id: StrictInt
	file_path: Path
	file_hash: StrictStr


class InstalledManagedMod(pydantic.BaseModel):
	mod_file_id: StrictInt
	installed_paths: list[Path]

	def all_paths_present(self) -> bool:
		return all(map(Path.is_dir, self.installed_paths))


class ManagedMod(pydantic.BaseModel):
	downloaded_mod: DownloadedManagedMod | None = Field(None)
	installed_mod: InstalledManagedMod | None = Field(None)

	def contains_info(self) -> bool:
		return self.downloaded_mod is not None or self.installed_mod is not None

	def has_mod_file_downloaded(self, requested_mod_file_id: int) -> bool:
		return self.downloaded_mod is not None and self.downloaded_mod.mod_file_id == requested_mod_file_id

	def has_mod_file_installed(self, requested_mod_file_id: int) -> bool:
		return (
				self.installed_mod is not None
				and self.installed_mod.mod_file_id == requested_mod_file_id
				and self.installed_mod.all_paths_present()
		)


class Storage(pydantic.BaseModel):
	games: dict[StrictStr, dict[StrictStr, ManagedMod]] = Field(default_factory=dict)

	def read_managed_mod(self, game_name_id: str, mod_name_id: str) -> ManagedMod | None:
		try:
			return self.games[game_name_id][mod_name_id]
		except KeyError:
			return None

	def write_managed_mod(self, game_name_id: str, mod_name_id: str, managed_mod: ManagedMod) -> None:
		self.games.setdefault(game_name_id, {})[mod_name_id] = managed_mod
