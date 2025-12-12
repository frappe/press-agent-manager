# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from press_base.agent.control_plane import ControlPlane
from press_base.agent.realtime import send_realtime_event_to_controlplane
from press_base.control_plane.api.remote_jobs import (
	RemoteJobCompletionDetails,
	RemoteJobStatus,
	RemoteJobStepStatus,
	RemoteJobStepSyncDetails,
)


class AgentJob(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		data: DF.Text | None
		end: DF.Datetime | None
		error: DF.SmallText | None
		is_submitted_to_controlplane: DF.Check
		job_type: DF.Data
		output: DF.Text | None
		start: DF.Datetime | None
		status: DF.Literal["Pending", "Running", "Success", "Failure"]
		submission_failure_count: DF.Int
		traceback: DF.LongText | None
		version_counter: DF.Int
	# end: auto-generated types

	@property
	def rq_job_id(self) -> str:
		return f"agent_job||{self.name}"

	def on_update(self):
		self.notify_controlplane()
		self.submit_to_controlplane_on_reaching_termination_state()
		self.increment_version_counter()

	def increment_version_counter(self):
		self.version_counter += 1
		self.db_update()

	def submit_to_controlplane_on_reaching_termination_state(self):
		if self.has_value_changed("status") and self.status in ["Success", "Failure"]:
			self.submit_to_controlplane_in_background()

	def submit_to_controlplane_in_background(self):
		if self.status not in ["Success", "Failure"]:
			return
		frappe.enqueue_doc(
			self.doctype,
			self.name,
			"submit_to_controlplane",
			job_id=f"agent_job||{self.name}||submit_to_controlplane",
			deduplicate=True,
			enqueue_after_commit=True,
		)

	def submit_to_controlplane(self):
		if self.is_submitted_to_controlplane:
			return

		frappe.get_value(self.doctype, self.name, "name", for_update=True)

		assert self.name
		steps = frappe.get_all("Agent Job Step", filters={"agent_job": self.name}, fields="*", as_list=False)

		try:
			ControlPlane().submit_job(
				self.name,
				RemoteJobCompletionDetails(
					status=RemoteJobStatus(self.status),
					start=self.start,
					end=self.end,
					output=self.output,
					data=self.data,
					error=self.error,
					traceback=self.traceback,
					version_counter=self.version_counter,
					steps=[
						RemoteJobStepSyncDetails(
							name=step.name,
							step_name=step.step_name,
							status=RemoteJobStepStatus(step.status),
							start=step.start,
							end=step.end,
							output=step.output,
							data=step.data,
							error=step.error,
							traceback=step.traceback,
							version_counter=step.version_counter,
						)
						for step in steps
					],
				),
			)
			frappe.db.set_value(
				self.doctype, self.name, "is_submitted_to_controlplane", True, update_modified=False
			)
		except Exception:
			frappe.log_error(
				"Failed to submit job to control plane",
				reference_doctype=self.doctype,
				reference_name=self.name,
			)

			frappe.db.set_value(
				self.doctype,
				self.name,
				"submission_failure_count",
				self.submission_failure_count + 1,
				update_modified=False,
			)

	def notify_controlplane(self):
		if self.is_new():
			return

		if self.status in ["Success", "Failure"]:
			return

		send_realtime_event_to_controlplane(
			"remote_job.sync_job",
			{
				"job_id": self.name,
				"data": {
					"status": self.status,
					"start": self.start,
					"end": self.end,
					"output": self.output,
					"data": self.data,
					"error": self.error,
					"traceback": self.traceback,
					"version_counter": self.version_counter,
				},
			},
		)

	def on_trash(self):
		frappe.db.delete("Agent Job Step", {"agent_job": self.name})


def submit_agent_jobs_to_controlplane():
	jobs = frappe.get_all(
		"Agent Job",
		filters={"is_submitted_to_controlplane": False, "status": ["in", ["Success", "Failure"]]},
		pluck="name",
		limit_page_length=50,
	)
	for job in jobs:
		try:
			job_doc: AgentJob = frappe.get_doc("Agent Job", job)  # type: ignore
			job_doc.submit_to_controlplane_in_background()
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
