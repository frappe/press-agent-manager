from typing import Any

import wrapt
from frappe.model.db_query import frappe
from pydantic import BaseModel, TypeAdapter


def pydantic_serialize(data: Any) -> Any:
	"""
	Convert any Pydantic V2 model, list/dict of models, or nested structure
	into a fully JSON-serializable object using Pydantic's serialization engine.
	"""
	if isinstance(data, BaseModel):
		return data.model_dump(mode="json")

	# Lists, dicts, tuples, sets, etc.
	adapter = TypeAdapter(type(data))
	return adapter.dump_python(data, mode="json")


def reconnect_on_failure():
	@wrapt.decorator
	def wrapper(wrapped, instance, args, kwargs):
		_ = instance
		try:
			return wrapped(*args, **kwargs)
		except Exception as e:
			if frappe.db.is_interface_error(e):  # type: ignore
				frappe.db.connect()
				return wrapped(*args, **kwargs)
			raise

	return wrapper
