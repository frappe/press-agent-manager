from __future__ import annotations

import threading
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

import frappe

T = TypeVar("T")


def in_site_context(site: str, fn: Callable[..., T]) -> Callable[..., T]:
	@wraps(fn)
	def wrapper(*args, **kwargs) -> T:
		try:
			with frappe.init_site(site):
				frappe.connect()
				try:
					result = fn(*args, **kwargs)
					frappe.db.commit()
					return result
				except Exception:
					frappe.db.rollback()
					raise
		finally:
			frappe.destroy()

	return wrapper


def debounce(wait: float) -> Callable[[Callable[..., T]], Callable[..., None]]:
	def decorator(fn: Callable[..., T]) -> Callable[..., None]:
		timer: threading.Timer | None = None
		lock = threading.Lock()

		@wraps(fn)
		def debounced(*args, **kwargs) -> None:
			nonlocal timer
			with lock:
				if timer:
					timer.cancel()
				timer = threading.Timer(wait, lambda: fn(*args, **kwargs))
				timer.start()

		return debounced

	return decorator
