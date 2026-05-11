# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import TYPE_CHECKING

import frappe

if TYPE_CHECKING:
	from press_agent_manager.iac.ansible import AnsibleStepResult
	from press_agent_manager.iac.doctype.ansible_play.ansible_play import AnsiblePlay


def run_command(host: str, command: str, port: int = 22, user: str = "root") -> AnsibleStepResult:
	from press_agent_manager.iac.ansible import AnsibleAdHoc

	adhoc = AnsibleAdHoc(sources=[host], port=port, user=user)
	results = adhoc.run(command)
	if host not in results:
		frappe.throw(f"Command failed on {host}. No results.")

	return results[host]


def run_playbook(host: str, playbook_yaml: str, port: int = 22, user: str = "root") -> list[AnsibleStepResult]:
	from press_agent_manager.iac.ansible import AnsibleAdHoc

	adhoc = AnsibleAdHoc(sources=[host], port=port, user=user)
	results = adhoc.run_playbook(playbook_yaml)
	return results.get(host, [])


def run_ansible_play(
	host: str,
	app: str,
	playbook_path: str,
	port: int = 22,
	user: str = "root",
	variables: dict | None = None,
	debug: bool = False,
	reference_doctype: str | None = None,
	reference_name: str | None = None,
	run_in_background: bool = False,
) -> AnsiblePlay:
	from press_agent_manager.iac.ansible import Ansible

	if (reference_doctype is None) != (reference_name is None):
		frappe.throw("Either both or neither reference_doctype and reference_name must be provided")

	playbook = Ansible(
		app=app,
		playbook_path=playbook_path,
		variables=variables or {},
		host=host,
		port=port,
		user=user,
		debug=debug,
		reference_doctype=reference_doctype,
		reference_name=reference_name,
	)

	return playbook.run(run_in_background)
