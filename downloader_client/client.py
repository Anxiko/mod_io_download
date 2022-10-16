import asyncio
from typing import Awaitable, Callable

import httpx
from tqdm import tqdm

from .task import DownloadResult, DownloadTask


class DownloaderClient:
	_download_tasks: list[DownloadTask]

	def __init__(self, download_tasks: list[DownloadTask]):
		self._download_tasks = download_tasks

	@staticmethod
	async def _download_task(
			client: httpx.AsyncClient, download_task: DownloadTask, callback: Callable[[int], None]
	) -> DownloadResult:
		with open(download_task.download_file_path, mode='wb') as f:
			try:
				response: httpx.Response
				async with client.stream('GET', download_task.download_url) as response:
					response.raise_for_status()
					total: int = int(response.headers['Content-Length'])
					chunk: bytes

					previous_downloaded_bytes: int = response.num_bytes_downloaded
					async for chunk in response.aiter_bytes():
						current_downloaded_bytes: int = response.num_bytes_downloaded
						callback(current_downloaded_bytes - previous_downloaded_bytes)
						previous_downloaded_bytes = current_downloaded_bytes

						f.write(chunk)

					return DownloadResult.result_ok(download_task, total)

			except Exception as e:
				return DownloadResult.result_error(download_task, e)

	async def download(self) -> list[DownloadResult]:
		if len(self._download_tasks) == 0:
			return []

		total_bytes: int = sum(map(DownloadTask.get_mod_file_size, self._download_tasks))
		with tqdm(
				total=total_bytes, unit_scale=True, unit_divisor=1024, unit='B', desc="Download progress"
		) as progress:
			async with httpx.AsyncClient(follow_redirects=True) as client:
				awaitables: list[Awaitable[DownloadResult]] = [
					self._download_task(client, download_task, progress.update)
					for download_task in self._download_tasks
				]

				results: list[DownloadResult] = await asyncio.gather(*awaitables)
			return results
