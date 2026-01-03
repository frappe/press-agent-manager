from contextlib import suppress

import frappe
import redis


def send_realtime_event_to_controlplane(
	event: str,
	message: dict | None = None,
	after_commit: bool = True,
):
	if after_commit:
		if not hasattr(frappe.local, "_outgoing_events_to_controlplane_log"):
			frappe.local._outgoing_events_to_controlplane_log = []
			frappe.db.after_commit.add(flush_realtime_log)
			frappe.db.after_rollback.add(clear_realtime_log)

		params = [event, message]
		if params not in frappe.local._outgoing_events_to_controlplane_log:
			frappe.local._outgoing_events_to_controlplane_log.append(params)


def flush_realtime_log():
	if not hasattr(frappe.local, "_outgoing_events_to_controlplane_log"):
		return
	for args in frappe.local._outgoing_events_to_controlplane_log:
		emit_via_redis(*args)

	clear_realtime_log()


def clear_realtime_log():
	if hasattr(frappe.local, "_outgoing_events_to_controlplane_log"):
		del frappe.local._outgoing_events_to_controlplane_log


def emit_via_redis(event: str, message: dict):
	from frappe.utils.background_jobs import get_redis_connection_without_auth

	with suppress(redis.ConnectionError):
		r = get_redis_connection_without_auth()
		r.publish(
			f"outgoing_events_to_controlplane||{frappe.local.site}",
			frappe.as_json({"event": event, "message": message}),
		)
