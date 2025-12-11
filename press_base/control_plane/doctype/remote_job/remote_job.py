# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

import frappe
from frappe.model.document import Document

from press_base.control_plane.utils import get_permission_query_conditions_for_doctype

if TYPE_CHECKING:
	from press_base.control_plane.doctype.remote_job_step.remote_job_step import RemoteJobStep


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

	def sync_job(
		self,
		status: Literal["Queued", "Pending", "Running", "Success", "Failure", "Rejected"] = "Queued",
		start: datetime | str | None = None,
		end: datetime | str | None = None,
		output: str | None = None,
		data: str | None = None,
		error: str | None = None,
		traceback: str | None = None,
	):
		self.status = status
		self.start = start
		self.end = end
		self.output = output
		self.data = data
		self.error = error
		self.traceback = traceback
		self.save()

	def sync_job_step(
		self,
		step_name: str,
		status: Literal["Pending", "Running", "Success", "Failure"] = "Pending",
		start: datetime | str | None = None,
		end: datetime | str | None = None,
		output: str | None = None,
		data: str | None = None,
		error: str | None = None,
		traceback: str | None = None,
	):
		step_doc = self.get_job_step(step_name)
		if not step_doc:
			step_doc = self.get_job_step(step_name)

		step_doc.status = status
		step_doc.start = start
		step_doc.end = end
		step_doc.output = output
		step_doc.data = data
		step_doc.error = error
		step_doc.traceback = traceback
		step_doc.save()

	def get_job_step(self, step_name: str) -> RemoteJobStep:
		step_doc_name = frappe.db.exists("Remote Job Step", {"remote_job": self.name, "step_name": step_name})
		if step_doc_name:
			return frappe.get_doc("Remote Job Step", step_doc_name)  # type: ignore

		step_doc: RemoteJobStep = frappe.new_doc("Remote Job Step")  # type: ignore
		assert self.name
		step_doc.step_name = step_name
		step_doc.status = "Pending"
		step_doc.remote_job = self.name
		step_doc.save()
		return step_doc

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
