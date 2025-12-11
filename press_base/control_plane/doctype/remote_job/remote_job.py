# Copyright (c) 2025, Frappe and contributors
# For license information, please see license.txt

# import frappe
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

	pass


get_permission_query_conditions = get_permission_query_conditions_for_doctype("Remote Job")
