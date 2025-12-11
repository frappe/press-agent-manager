# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from press_base.control_plane.utils import get_permission_query_conditions_for_doctype


class RemoteJob(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		agent: DF.Link | None
		data: DF.LongText | None
		duration: DF.Time | None
		end: DF.Datetime | None
		error: DF.SmallText | None
		job_type: DF.Link
		output: DF.LongText | None
		rejection_reason: DF.Data | None
		request_data: DF.JSON | None
		start: DF.Datetime | None
		status: DF.Literal["Queued", "Pending", "Running", "Success", "Failure", "Rejected"]
		traceback: DF.LongText | None
	# end: auto-generated types

	def on_update(self):
		if not self.is_new() and self.has_value_changed("status") and self.status == "Queued":
			self._notify_agent_about_new_job()

	def after_insert(self):
		self._notify_agent_about_new_job()

	def _notify_agent_about_new_job(self):
		if not self.agent:
			# TODO: broadcast to everyone
			return

		frappe.publish_realtime(
			"remote_job.new",
			user=frappe.db.get_value("Agent", self.agent, "user", cache=True),  # type: ignore
			after_commit=True,
		)


get_permission_query_conditions = get_permission_query_conditions_for_doctype("Remote Job")
