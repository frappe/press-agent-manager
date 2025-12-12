from __future__ import annotations

import contextlib
import json
import traceback
from time import sleep
from typing import TYPE_CHECKING, TypeVar

import click
import frappe
import socketio
from frappe.commands import get_site, pass_context
from frappe.utils.background_jobs import get_redis_connection_without_auth
from frappe.utils.bench_helper import CliCtxObj

from press_base.agent.control_plane import poll_queued_jobs
from press_base.commands.utils import debounce, in_site_context

if TYPE_CHECKING:
	from press_base.agent.doctype.agent_settings.agent_settings import AgentSettings

T = TypeVar("T")

EVENT_HANDLERS = {
	"remote_job.new": {"handler": poll_queued_jobs, "debounce": 0.5},
}


@click.command("run-socketio-event-manager")
@click.option("--site", help="site name")
@pass_context
def manage_socket_io_events_cmd(context: CliCtxObj, site: str | None = None) -> None:
	site = site or get_site(context)

	while True:
		try:
			with frappe.init_site(site):
				frappe.connect()
				manage_socket_io_events()
		except KeyboardInterrupt:
			print("Exiting...")
			break
		except Exception as e:
			print(f"Failed to listen for Socket.IO events: {e}")
			traceback.print_exc()
			sleep(1)


def manage_socket_io_events() -> None:
	settings: AgentSettings = frappe.get_single("Agent Settings")  # type: ignore
	assert settings.enabled, "Agent is not enabled from Settings"

	site = frappe.local.site
	sio = socketio.Client()
	redis = get_redis_connection_without_auth()
	pubsub = redis.pubsub()

	# Setup event handlers for incoming events from controlplane
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

	# Listen for events to send to controlplane
	def send_events_to_sio(message: dict):
		try:
			data = json.loads(message["data"])
			sio.emit(
				data["event"],
				data["message"],
				namespace=settings.socketio_namespace,
			)
		except Exception:
			frappe.log_error("Failed to send realtime event to controlplane")

	pubsub.subscribe(**{f"outgoing_events_to_controlplane||{frappe.local.site}": send_events_to_sio})

	thread = None
	try:
		thread = pubsub.run_in_thread(sleep_time=0.001)
		sio.wait()
	finally:
		with contextlib.suppress(Exception):
			if thread:
				thread.stop()
				thread.join()

		with contextlib.suppress(Exception):
			sio.disconnect()
