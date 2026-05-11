# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class AnsibleTask(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		duration: DF.Duration | None
		end: DF.Datetime | None
		error: DF.Code | None
		exception: DF.Code | None
		output: DF.Code | None
		play: DF.Link | None
		result: DF.Code | None
		role: DF.Data | None
		start: DF.Datetime | None
		status: DF.Literal["Pending", "Running", "Success", "Failure"]
		task: DF.Data | None
	# end: auto-generated types

	pass
