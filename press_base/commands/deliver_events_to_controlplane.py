from __future__ import annotations

import traceback
from collections.abc import Callable
from functools import wraps
from time import sleep
from typing import TYPE_CHECKING, TypeVar

import click
import frappe
import socketio
from frappe.commands import get_site, pass_context
from frappe.utils.bench_helper import CliCtxObj

from press_base.agent.control_plane import poll_queued_jobs
from press_base.commands.utils import debounce, in_site_context


@click.command("deliver-events-to-controlplane")
@click.option("--site", help="site name")
@pass_context
def deliver_events_to_controlplane(context: CliCtxObj, site: str | None = None) -> None:
	pass
