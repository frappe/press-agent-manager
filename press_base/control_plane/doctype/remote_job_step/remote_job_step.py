# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


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
		job_type: DF.Data
		output: DF.LongText | None
		remote_job: DF.Link
		start: DF.Datetime | None
		status: DF.Literal["Pending", "Running", "Success", "Failure"]
		traceback: DF.LongText | None
	# end: auto-generated types

	pass
