import threading
from functools import wraps
from typing import Any

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
