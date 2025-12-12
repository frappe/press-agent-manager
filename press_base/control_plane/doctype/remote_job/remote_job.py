# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal

import frappe
from frappe.model.document import Document
from frappe.utils import cint, get_datetime

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
		version_counter: DF.Int
	# end: auto-generated types

	def on_update(self):
		if not self.is_new() and self.has_value_changed("status") and self.status == "Queued":
			self._notify_agent_about_new_job()

		if (
			not self.is_new()
			and (previous := self.get_doc_before_save())
			and previous.status in ["Success", "Failure"]
		):
			frappe.throw("Job cannot be updated anymore as it is already completed")

		self.calculate_duration()
		if not self.is_new():
			self.process_callback()

	def calculate_duration(self):
		if (
			self.start
			and self.end
			and ((self.has_value_changed("start") or self.has_value_changed("end")) or not self.duration)
		):
			self.duration = cint((get_datetime(self.end) - get_datetime(self.start)).total_seconds())  # type: ignore
			self.db_update()

	def after_insert(self):
		self._notify_agent_about_new_job()

	def sync_info(
		self,
		status: Literal["Queued", "Pending", "Running", "Success", "Failure", "Rejected"] = "Queued",
		start: datetime | None = None,
		end: datetime | None = None,
		output: str | None = None,
		data: str | None = None,
		error: str | None = None,
		traceback: str | None = None,
		version_counter: int = 0,
	):
		if self.status in ["Success", "Failure"]:
			frappe.throw("Job status cannot be updated as it is already completed")

		if self.version_counter != 0 and self.version_counter >= version_counter:
			return False, self

		self.status = status
		self.start = start
		self.end = end
		self.output = output
		self.data = data
		self.error = error
		self.traceback = traceback
		self.version_counter = version_counter
		self.save()

	def sync_job_step(
		self,
		name: str,
		step_name: str,
		status: Literal["Pending", "Running", "Success", "Failure"] = "Pending",
		start: datetime | None = None,
		end: datetime | None = None,
		output: str | None = None,
		data: str | None = None,
		error: str | None = None,
		traceback: str | None = None,
		version_counter: int = 0,
	):
		step_doc = self.get_job_step(name, step_name)
		if step_doc.version_counter != 0 and step_doc.version_counter >= version_counter:
			return False, step_doc

		step_doc.status = status
		step_doc.start = start
		step_doc.end = end
		step_doc.output = output
		step_doc.data = data
		step_doc.error = error
		step_doc.traceback = traceback
		step_doc.version_counter = version_counter
		step_doc.save()

	def get_job_step(self, name: str, step_name: str, for_update: bool = True) -> RemoteJobStep:
		try:
			# Try to get with for_update=True to lock the row
			return frappe.get_doc("Remote Job Step", name, for_update=for_update)  # type: ignore
		except frappe.DoesNotExistError:
			# Only create if it truly doesn't exist
			step_doc: RemoteJobStep = frappe.new_doc("Remote Job Step")  # type: ignore
			step_doc.name = name
			step_doc.flags.name_set = True
			step_doc.step_name = step_name
			step_doc.status = "Pending"
			assert self.name
			step_doc.remote_job = self.name
			step_doc.version_counter = 0
			try:
				step_doc.insert()
			except frappe.DuplicateEntryError:
				# Race condition: another transaction created it
				return frappe.get_doc("Remote Job Step", name, for_update=for_update)  # type: ignore
			return step_doc

	def process_callback(self):
		try:
			job_type = self.job_type
			status = self.status

			hooks = frappe.get_hooks("remote_job_callback_handlers") or {}

			if job_type not in hooks:
				return

			# hooks[job_type] is a list of pairs → (status_list_or_star, dotted_path)
			for statuses, dotted_path in hooks[job_type]:
				# "*" means all statuses allowed
				if statuses == "*" or status in statuses:
					frappe.call(dotted_path, self)

		except Exception:
			frappe.log_error(
				title="Remote Job Callback Failed",
				reference_doctype=self.doctype,
				reference_name=self.name,
			)
			raise

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
