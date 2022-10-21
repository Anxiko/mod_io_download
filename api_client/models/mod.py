from typing import Callable

from pydantic import BaseModel, StrictInt, StrictStr

from .mod_file import ModFile
from .platform import TargetPlatform


class ModPlatform(BaseModel):
	platform: TargetPlatform
	modfile_live: StrictInt

	@classmethod
	def filter_by_platform(cls, platform: TargetPlatform) -> Callable[['ModPlatform'], bool]:
		def f(mod_platform: 'ModPlatform') -> bool:
			return mod_platform.platform == platform

		return f

	def get_platform(self) -> TargetPlatform:
		return self.platform


class Mod(BaseModel):
	id: StrictInt
	game_id: StrictInt
	name: StrictStr
	name_id: StrictStr
	modfile: ModFile
	platforms: list[ModPlatform]
	visible: bool

	def get_platform(self, platform: TargetPlatform) -> ModPlatform:
		return next(filter(
			ModPlatform.filter_by_platform(platform),
			self.platforms
		))

	def supported_platforms(self) -> set[TargetPlatform]:
		return set(map(ModPlatform.get_platform, self.platforms))

	def is_available(self) -> bool:
		"""Mod is available for download. Only checking visibility for now"""
		return self.visible
