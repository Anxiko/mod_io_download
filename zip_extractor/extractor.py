import os
import shutil
from functools import partial
from logging import Logger
from pathlib import Path
from typing import Iterable
from zipfile import ZipFile

import logger

logger: Logger = logger.get_logger(__name__)


class ZipExtractor:
	_PALLET_FILE: str = "pallet.json"
	_PLATFORM_KEYWORDS: str = ['win', 'pc']

	_extractions_path: Path
	_installations_path: Path

	def __init__(self, extractions_path: Path, installations_path: Path):
		self._extractions_path = extractions_path
		self._installations_path = installations_path

	@staticmethod
	def _nuke(p: Path) -> None:
		if not p.exists():
			return

		if p.is_dir():
			shutil.rmtree(p)
		elif p.is_file():
			os.remove(p)
		else:
			raise TypeError(f"Can't remove {p}: is not a file or directory")

	def _get_path_for_mod_extraction(self, mod_file) -> Path:
		name_without_extension: str = mod_file.stem
		target_path: Path = self._extractions_path / name_without_extension

		self._nuke(target_path)
		os.makedirs(target_path)
		return target_path

	@staticmethod
	def _flatten_lists(lists: Iterable[Iterable[Path]]) -> list[Path]:
		return [
			p
			for l in lists
			for p in l
		]

	def _locate_possible_content_folders(self, p: Path) -> list[Path]:
		maybe_pallet: Path = p / self._PALLET_FILE
		if maybe_pallet.is_file():
			return [p]

		return self._flatten_lists(
			map(
				self._locate_possible_content_folders,
				filter(Path.is_dir, p.iterdir())
			)
		)

	def _has_platform_keyword(self, root: Path, p: Path) -> bool:
		rel_path: str = str(p.relative_to(root)).lower()
		return any(keyword in rel_path for keyword in self._PLATFORM_KEYWORDS)

	def _get_selected_content_folder(self, extraction_path: Path) -> Path | None:
		possible_content_folders: list[Path] = self._locate_possible_content_folders(extraction_path)

		if len(possible_content_folders) == 1:
			return possible_content_folders[0]

		if len(possible_content_folders) == 0:
			logger.warning(f"Could not locate {self._PALLET_FILE} in {extraction_path}")
			return None

		platform_keyword_content_folders: list[Path] = list(
			filter(partial(self._has_platform_keyword, extraction_path), possible_content_folders))

		if len(platform_keyword_content_folders) == 0:
			logger.warning(
				f"Found too many content folders {possible_content_folders},"
				f" but could not find platform keywords {self._PLATFORM_KEYWORDS}"
				f" in any of them."
			)
			return None

		if len(platform_keyword_content_folders) == 1:
			return platform_keyword_content_folders[0]

		logger.warning(
			f"Found too many content folders {possible_content_folders},"
			f" and found the platform keywords {self._PLATFORM_KEYWORDS}"
			f" in too many of them: {platform_keyword_content_folders}"
		)
		return None

	@staticmethod
	def _extract_zip(zip_path: Path, output_path: Path) -> None:
		with ZipFile(zip_path, mode='r') as z:
			z.extractall(output_path)

	@classmethod
	def _copy_to_mods_dir(cls, content: Path, mods_dir: Path) -> Path:
		result_dir: Path = mods_dir / content.name
		cls._nuke(result_dir)
		shutil.copytree(content, result_dir)
		return result_dir

	def _extract_mod(self, mod_file: Path) -> Path:
		if not mod_file.is_file():
			logger.error(f"Given mod file {mod_file} is not a file")
			raise ValueError(f"Not a file: {mod_file}")

		target_path: Path = self._get_path_for_mod_extraction(mod_file)
		self._extract_zip(mod_file, target_path)
		return target_path

	def _install_mod(self, extracted_path: Path) -> Path | None:
		content_path: Path | None = self._get_selected_content_folder(extracted_path)
		if content_path is None:
			return None

		return self._copy_to_mods_dir(content_path, self._installations_path)

	def extract_and_install(self, mod_file: Path) -> Path | None:
		extracted_path: Path = self._extract_mod(mod_file)
		installation_path: Path | None = self._install_mod(extracted_path)
		return installation_path
