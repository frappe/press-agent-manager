from __future__ import annotations

import traceback
from collections.abc import Callable
from functools import wraps
from time import sleep
from typing import TYPE_CHECKING, TypeVar

import click
import frappe
import socketio
from frappe.commands import get_site, pass_context
from frappe.utils.bench_helper import CliCtxObj

from press_base.agent.control_plane import poll_queued_jobs
from press_base.commands.utils import debounce, in_site_context

if TYPE_CHECKING:
	from press_base.agent.doctype.agent_settings.agent_settings import AgentSettings

T = TypeVar("T")

EVENT_HANDLERS = {
	"remote_job.new": {"handler": poll_queued_jobs, "debounce": 0.5},
}


@click.command("listen-for-socketio-events")
@click.option("--site", help="site name")
@pass_context
def listen_for_socketio_events_cmd(context: CliCtxObj, site: str | None = None) -> None:
	site = site or get_site(context)

	while True:
		try:
			with frappe.init_site(site):
				frappe.connect()
				listen_for_socketio_events()
		except KeyboardInterrupt:
			print("Exiting...")
			break
		except Exception as e:
			print(f"Failed to listen for Socket.IO events: {e}")
			traceback.print_exc()
			sleep(1)


def listen_for_socketio_events() -> None:
	settings: AgentSettings = frappe.get_single("Agent Settings")  # type: ignore
	assert settings.enabled, "Agent is not enabled from Settings"

	site = frappe.local.site
	sio = socketio.Client()

	for event, config in EVENT_HANDLERS.items():
		handler = in_site_context(site, config["handler"])
		if debounce_wait := config.get("debounce"):
			handler = debounce(debounce_wait)(handler)
		sio.on(event, namespace=settings.socketio_namespace, handler=handler)

	sio.connect(
		settings.controlplane_socketio_url,
		namespaces=[settings.socketio_namespace],
		headers={
			"Authorization": f"token {settings.controlplane_api_key}:{settings.get_password('controlplane_api_secret')}",
			"Origin": settings.controlplane_socketio_url,
		},
		retry=True,
	)

	try:
		sio.wait()
	finally:
		sio.disconnect()
