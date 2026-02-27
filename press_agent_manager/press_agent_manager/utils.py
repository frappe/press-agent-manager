import os
import shlex
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

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


def resolve_host_path(path: str | os.PathLike[str] | Path) -> Path:
	p = Path(os.fspath(path))

	if not p.is_absolute():
		raise ValueError(f"Relative paths are not allowed: {path!r}")

	rootfs = os.environ.get("HOST_ROOTFS")
	if not rootfs:
		return p

	return Path(rootfs) / p.relative_to("/")


def _execute_command_impl(*popenargs: Any, **kwargs: Any):
	if "args" in kwargs:
		cmd = kwargs["args"]
		use_kwargs = True
	elif popenargs:
		cmd = popenargs[0]
		use_kwargs = False
	else:
		return subprocess.run(*popenargs, **kwargs)

	shell = bool(kwargs.get("shell"))
	executable = kwargs.get("executable")
	user_env = kwargs.get("env")

	rootfs = os.environ.get("HOST_ROOTFS")
	if not rootfs:
		return subprocess.run(*popenargs, **kwargs)

	if isinstance(cmd, bytes):
		cmd = cmd.decode()

	base_env = {
		"PATH": os.environ.get(
			"HOST_ENV_PATH",
			"/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin:/usr/local/go/bin",
		),
		"HOME": "/root",
		"TERM": "xterm",
	}
	if user_env:
		base_env.update(user_env)

	if isinstance(cmd, (list, tuple)) and list(cmd[:2]) == ["chroot", rootfs]:
		return subprocess.run(*popenargs, **kwargs)

	prefix = ["chroot", rootfs, "/usr/bin/env", "-i"]
	prefix.extend(f"{k}={v}" for k, v in base_env.items())

	if shell:
		shell_prog = executable or "/bin/sh"
		shell_cmd = cmd if isinstance(cmd, str) else shlex.join(cmd)

		new_cmd = [*prefix, shell_prog, "-c", shell_cmd]
		kwargs["shell"] = False
		kwargs.pop("executable", None)
	else:
		if isinstance(cmd, str):
			cmd = shlex.split(cmd)
		new_cmd = [*prefix, *cmd] if isinstance(cmd, (list, tuple)) else cmd

	if use_kwargs:
		kwargs["args"] = new_cmd
	else:
		popenargs = (new_cmd, *popenargs[1:])

	return subprocess.run(*popenargs, **kwargs)


if TYPE_CHECKING:
	from subprocess import run as execute_command
else:
	execute_command = _execute_command_impl
