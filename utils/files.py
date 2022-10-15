import os
import shutil
from pathlib import Path


def nuke_path(p: Path) -> None:
	if not p.exists():
		return

	if p.is_dir():
		shutil.rmtree(p)
	elif p.is_file():
		os.remove(p)
	else:
		raise TypeError(f"Can't remove {p}: is not a file or directory")
