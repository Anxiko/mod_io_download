import asyncio
from functools import partial
from typing import Awaitable

import httpx

from .task import DownloadResult, DownloadTask


class DownloaderClient:
	_download_tasks: list[DownloadTask]

	def __init__(self, download_tasks: list[DownloadTask]):
		self._download_tasks = download_tasks

	@staticmethod
	async def _download_task(client: httpx.AsyncClient, download_task: DownloadTask) -> DownloadResult:
		with open(download_task.download_file_path, mode='wb') as f:
			try:
				response: httpx.Response
				async with client.stream('GET', download_task.download_url) as response:
					response.raise_for_status()
					total: int = int(response.headers['Content-Length'])
					chunk: bytes
					async for chunk in response.aiter_bytes():
						f.write(chunk)
					return DownloadResult.result_ok(download_task, total)

			except Exception as e:
				return DownloadResult.result_error(download_task, e)

	@classmethod
	def _to_future(
			cls, client: httpx.AsyncClient, download_task: DownloadTask
	) -> Awaitable[DownloadResult]:
		return cls._download_task(client, download_task)

	async def download(self) -> list[DownloadResult]:
		async with httpx.AsyncClient(follow_redirects=True) as client:
			awaitables: list[Awaitable[Awaitable[DownloadResult]]] = list(map(
				partial(self._to_future, client),
				self._download_tasks
			))
			results: list[DownloadResult] = await asyncio.gather(*awaitables)
			return results
