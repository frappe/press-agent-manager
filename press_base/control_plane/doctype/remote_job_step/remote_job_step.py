# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document
from frappe.utils import cint, get_datetime


class RemoteJobStep(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		data: DF.LongText | None
		duration: DF.Time | None
		end: DF.Datetime | None
		error: DF.SmallText | None
		output: DF.LongText | None
		remote_job: DF.Link
		start: DF.Datetime | None
		status: DF.Literal["Pending", "Running", "Success", "Failure", "Skipped"]
		step_name: DF.Data
		traceback: DF.LongText | None
		version_counter: DF.Int
	# end: auto-generated types

	def on_update(self):
		self.calculate_duration()

	def calculate_duration(self):
		if (
			self.start
			and self.end
			and ((self.has_value_changed("start") or self.has_value_changed("end")) or not self.duration)
		):
			self.duration = cint((get_datetime(self.end) - get_datetime(self.start)).total_seconds())  # type: ignore
			self.db_update()
