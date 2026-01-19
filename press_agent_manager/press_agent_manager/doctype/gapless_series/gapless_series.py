# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document


class GaplessSeries(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		available_values: DF.JSON | None
		current_value: DF.Int
		end: DF.Int
		start: DF.Int
		step: DF.Int
		title: DF.Data
	# end: auto-generated types

	def on_update(self):
		if self.is_new():
			return

		if self.has_value_changed("end") and self.end < self.start:
			frappe.throw("End value cannot be less than start value")

	def get_next_value(self) -> int:
		series_data = frappe.db.get_value(
			self.doctype,
			self.name,
			fieldname=["current_value", "available_values", "end"],
			for_update=True,
			as_dict=True,
		)

		assert series_data, f"Series {self.name} not found"

		available_values = json.loads(series_data.available_values or "[]")  # type: ignore
		current_value: int = series_data.current_value  # type: ignore

		if available_values:
			val = min(available_values)
			available_values.remove(val)
			new_current_value = current_value
		else:
			val = current_value + self.step
			new_current_value = val

		if val > series_data.end:  # type: ignore
			frappe.throw("Series exhausted")

		assert self.name, f"Series {self.name} not found"
		frappe.db.set_value(
			self.doctype,
			self.name,
			{
				"current_value": new_current_value,  # type: ignore
				"available_values": json.dumps(available_values),
			},
			update_modified=False,
		)

		return val

	def return_value(self, value: int):
		series_data = frappe.db.get_value(
			self.doctype,
			self.name,
			fieldname=["current_value", "available_values"],
			for_update=True,
			as_dict=True,
		)

		assert series_data, f"Series {self.name} not found"

		current_value: int = series_data.current_value  # type: ignore
		available_values = set(json.loads(series_data.available_values or "[]"))  # type: ignore

		if value > current_value:
			frappe.throw(f"Cannot release {value} as it is greater than current value {current_value}")

		if value in available_values:
			return

		available_values.add(value)

		assert self.name, f"Series {self.name} not found"
		frappe.db.set_value(
			self.doctype,
			self.name,
			"available_values",
			json.dumps(list(available_values)),
			update_modified=False,
		)


def init_gapless_series(
	name: str,
	start_value: int,
	pool_size: int,
	step: int = 1,
	description: str | None = None,
) -> GaplessSeries:
	return frappe.get_doc(
		{
			"doctype": "Gapless Series",
			"name": name,
			"title": description or name or "",
			"start": start_value,
			"step": step,
			"end": start_value + pool_size - 1,
			"current_value": start_value,
		},
	).insert()  # type: ignore


def update_pool_size(series_name: str, new_size: int):
	series: GaplessSeries = frappe.get_doc("Gapless Series", series_name, for_update=True)  # type: ignore
	series.end = new_size
	series.save(ignore_permissions=True)


def get_next_value_from_pool(series_name: str) -> int:
	series: GaplessSeries = frappe.get_doc("Gapless Series", series_name)  # type: ignore
	return series.get_next_value()


def return_value_to_pool(series_name: str, value: int):
	series: GaplessSeries = frappe.get_doc("Gapless Series", series_name)  # type: ignore
	series.return_value(value)
