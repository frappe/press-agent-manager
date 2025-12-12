from __future__ import annotations

import contextlib
import io
import traceback
from contextlib import redirect_stderr, redirect_stdout
from contextvars import ContextVar
from typing import TYPE_CHECKING

import frappe
from frappe.utils.background_jobs import enqueue as frappe_enqueue
from frappe.utils.data import now_datetime

if TYPE_CHECKING:
	from collections.abc import Callable

	from press_base.agent.doctype.agent_job.agent_job import AgentJob
	from press_base.agent.doctype.agent_job_step.agent_job_step import AgentJobStep

agent_job_context: ContextVar[AgentJob] = ContextVar("agent_job_context")
agent_job_step_context: ContextVar[AgentJobStep | None] = ContextVar("agent_job_step_context", default=None)
agent_job_flush_output: ContextVar[Callable | None] = ContextVar("agent_job_flush_output", default=None)

"""
Agent Job & Step Integration

> How to Enqueue Job ?
enqueue(
	<job_type>, # Name of the job
	<method>, # Pass callable instance
	<queue>, # Queue name
	<timeout>, # Timeout in seconds
)

The enqueue method is a wrapper around frappe's enqueue method.

> How to define metadata for Step ?
You need to add @step decarotar to the method you want to run as a step.

@step("<step_name>")
def sample():
	pass

With even @step decorator, the function can be used as normal function.

> Logging

You can use print(...) statement directly.
The output will be logged in the Agent Job Step log.

> Terminology in Agent Job & Step

- data : Returned value from the step function or job function
- output : Logged output from the step function or job function (print will be logged here also)
- error : Logged error from the step function or job function
- traceback : Logged traceback from the step function or job function
"""


def enqueue(
	job_type: str,
	method: Callable,
	agent_job_name: str | None = None,
	queue: str = "default",
	timeout: int | None = None,
	*,
	at_front: bool = False,
	at_front_when_starved=False,
	**kwargs,
) -> AgentJob:
	if not job_type:
		raise ValueError("Job type is required")

	# Check if the method is decorated with @step
	if getattr(method, "__is_step_decorator__", False):
		frappe.throw(
			title="Invalid Function",
			msg=(
				f"Cannot enqueue @step decorated function '{getattr(method, '__name__', 'unknown')}'.\n\n"
				"The @step decorator cannot be used on the top-level function passed to enqueue() "
				"because it creates closures that cannot be pickled.\n\n"
			),
		)

	# If agent job exists, no need to enqueue
	if agent_job_name and frappe.db.exists("Agent Job", agent_job_name):
		return frappe.get_doc("Agent Job", agent_job_name)  # type: ignore

	agent_job: AgentJob = frappe.new_doc("Agent Job")  # type: ignore
	agent_job.job_type = job_type
	agent_job.status = "Pending"
	agent_job.name = agent_job_name
	agent_job.flags.name_set = agent_job_name is not None
	agent_job.insert()

	# remove agent_job_name and method_to_run from kwargs
	kwargs.pop("agent_job_name", None)
	kwargs.pop("method_to_run", None)

	frappe_enqueue(
		execute_agent_job,
		queue=queue,
		timeout=timeout,
		enqueue_after_commit=True,
		job_id=agent_job.rq_job_id,
		on_success=None,
		on_failure=None,
		at_front=at_front,
		at_front_when_starved=at_front_when_starved,
		# kwargs
		method_to_run=method,
		agent_job_name=agent_job.name,
		**kwargs,
	)
	return agent_job


def step(title: str):
	"""
	Decorator to mark a function as a step in an agent job.

	When a function decorated with @step runs within an agent job context, it will:
	- Create/update an Agent Job Step record
	- Capture all stdout/stderr output (including print statements)
	- Track execution time, status, and any errors
	- Support real-time output flushing via flush_output()

	Args:
		title: Display name for the step in the job log

	Usage:
		@step("Process Data")
		def process_data():
			print("Processing...")
			flush_output()  # Optional: commit logs in real-time
			return result

	Important:
		- @step decorated functions work anywhere in your codebase
		- They automatically detect if running within a job context
		- If no job context exists, they execute as normal functions

		⚠️ DO NOT use @step on the function you pass directly to enqueue():

		❌ WRONG:
			@step("My Job")
			def my_job():
				pass
			enqueue("type", my_job)  # Causes pickle errors!

		✅ CORRECT:
			def my_job():
				process_step()

			@step("Process Step")
			def process_step():
				pass

			enqueue("type", my_job)  # Works perfectly
	"""

	def decorator(func):
		def wrapper(*args, **kwargs):
			try:
				agent_job = agent_job_context.get()
			except LookupError:
				frappe.log_error("Agent Job context not set")
				return func(*args, **kwargs)

			assert agent_job, "Agent Job context not set"

			result = None
			success = False
			data = None
			error = None
			traceback_data = None
			output_buffer = io.StringIO()

			step = _get_or_create_agent_step(agent_job, title)
			agent_job_step_context.set(step)

			def flush_output_impl():
				"""
				Flush current output buffer to database
				This is meant to be used for realtime log update of steps
				"""
				try:
					current_output = output_buffer.getvalue()
					if current_output:
						step.output = current_output
						step.save()
						frappe.db.commit()
				except Exception as e:
					frappe.log_error(f"Error flushing output: {e}")

			# Store previous flush_output and set new one
			old_flush = agent_job_flush_output.get()
			agent_job_flush_output.set(flush_output_impl)

			try:
				step.status = "Running"
				step.start = now_datetime()
				step.save()
				frappe.db.commit()

				# capture stdout and stderr
				with redirect_stdout(output_buffer), redirect_stderr(output_buffer):
					data = func(*args, **kwargs)

				success = True
			except Exception as e:
				error = str(e)
				traceback_data = traceback.format_exc()

				# Restore previous flush_output
				agent_job_flush_output.set(old_flush)

				raise e
			finally:
				step.status = "Success" if success else "Failure"
				if data or not step.data:
					step.data = data or ""

				step.output = output_buffer.getvalue()
				step.error = error
				step.traceback = traceback_data
				step.end = now_datetime()
				step.duration = int((step.end - step.start).total_seconds())  # type: ignore
				step.save()
				frappe.db.commit()

				# Reset step context
				agent_job_step_context.set(None)

				# Restore previous flush_output
				agent_job_flush_output.set(old_flush)

			return result

		# Mark this as a step-decorated function
		wrapper.__is_step_decorator__ = True  # type: ignore
		return wrapper

	return decorator


def flush_output():
	"""Alias function to flush output from current step context"""
	flush_fn = agent_job_flush_output.get()
	if flush_fn:
		flush_fn()


def update_step_data(data: str, replace: bool = False):
	step = agent_job_step_context.get()
	if step:
		step.data = data if replace else (step.data or "") + data
		step.save()
		frappe.db.commit()


def update_job_data(data: str, replace: bool = False):
	with contextlib.suppress(LookupError):
		job = agent_job_context.get()
		job.data = data if replace else (job.data or "") + data
		job.save()
		frappe.db.commit()


def execute_agent_job(agent_job_name: str, method_to_run: Callable, **kwargs):
	if not frappe.db.exists("Agent Job", agent_job_name):
		return

	agent_job: AgentJob = frappe.get_doc("Agent Job", agent_job_name, for_update=True)  # type: ignore
	agent_job_context.set(agent_job)

	success = False
	data = None
	error = None
	traceback_data = None
	output_buffer = io.StringIO()

	try:
		# Set status to Running
		agent_job.start = now_datetime()
		agent_job.status = "Running"
		agent_job.save()
		frappe.db.commit()

		# capture stdout and stderr
		with redirect_stdout(output_buffer), redirect_stderr(output_buffer):
			data = method_to_run(**kwargs)
		success = True
	except Exception as e:
		success = False
		error = str(e)
		traceback_data = traceback.format_exc()
	finally:
		agent_job.status = "Success" if success else "Failure"
		agent_job.data = str(data or "")
		agent_job.output = output_buffer.getvalue()
		agent_job.error = error or ""
		agent_job.traceback = traceback_data or ""
		agent_job.end = now_datetime()
		agent_job.duration = int((agent_job.end - agent_job.start).total_seconds())  # type: ignore
		agent_job.save()
		frappe.db.commit()


def _get_or_create_agent_step(job: AgentJob, step_name: str) -> AgentJobStep:
	existing_step = frappe.db.exists("Agent Job Step", {"job": job.name, "name": step_name})
	if existing_step:
		step: AgentJobStep = frappe.get_doc("Agent Job Step", existing_step, for_update=True)  # type: ignore
	else:
		step: AgentJobStep = frappe.new_doc("Agent Job Step")  # type: ignore
		step.agent_job = job.name  # type: ignore
		step.step_name = step_name
		step.insert()
		frappe.db.commit()

	return step
