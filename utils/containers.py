from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


def flatten_iterable(iterable_of_iterables: Iterable[Iterable[T]]) -> list[T]:
	return [
		element
		for iterable in iterable_of_iterables
		for element in iterable
	]


def binary_partition(elements: Iterable[T], predicate: Callable[[T], bool]) -> tuple[list[T], list[T]]:
	elements_true: list[T] = []
	elements_false: list[T] = []

	for e in elements:
		if predicate(e):
			elements_true.append(e)
		else:
			elements_false.append(e)

	return elements_true, elements_false
