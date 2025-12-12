from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import frappe

if TYPE_CHECKING:
	from press_base.control_plane.doctype.agent.agent import Agent


def get_current_agent(get_doc: bool = False) -> str | Agent:
	if frappe.session.user == "Guest":
		frappe.throw("Not Permitted", frappe.AuthenticationError)

	agent_name = frappe.db.exists("Agent", {"user": frappe.session.user, "enabled": 1})
	if not agent_name:
		frappe.throw("Agent not found", frappe.DoesNotExistError)

	if get_doc:
		return frappe.get_doc("Agent", agent_name)  # type: ignore
	return agent_name  # type: ignore


def get_permission_query_conditions_for_doctype_and_user(doctype, user):
	if not user:
		user = frappe.session.user

	user_type = frappe.db.get_value("User", user, "user_type", cache=True)
	if user_type == "System User":
		return ""

	agent = get_current_agent()
	return f"(`tab{doctype}`.`agent` = {frappe.db.escape(agent)})"


def get_permission_query_conditions_for_doctype(doctype):
	return partial(get_permission_query_conditions_for_doctype_and_user, doctype)
