const { get_url } = require("../../frappe/realtime/utils");

function press_agent_manager_event_handler(socket) {
	socket.on("remote_job.sync_job", (message) => {
		let job_id = message.job_id;
		let data = message.data;
		send_request(socket, {
			path: `/api/control-plane/remote-jobs/${job_id}/sync-job`,
			method: "POST",
			json: data,
		});
	});

	socket.on("remote_job.sync_step", (message) => {
		let job_id = message.job_id;
		let data = message.data;
		send_request(socket, {
			path: `/api/control-plane/remote-jobs/${job_id}/sync-step`,
			method: "POST",
			json: data,
		});
	});
}

// Helper methods
function send_request(
	socket,
	{ path, method = "GET", params = {}, json = null, headers = {}, ...rest }
) {
	const query = new URLSearchParams(params);
	if (query.toString()) {
		path = `${path}?${query.toString()}`;
	}

	let finalHeaders = { ...headers };
	if (socket.authorization_header) {
		finalHeaders["Authorization"] = socket.authorization_header;
	} else if (socket.sid) {
		finalHeaders["Cookie"] = `sid=${socket.sid}`;
	}

	let body = rest.body;
	if (json !== null) {
		finalHeaders["Content-Type"] = "application/json";
		body = JSON.stringify(json);
	}

	return fetch(get_url(socket, path), {
		method,
		headers: finalHeaders,
		body,
		...rest,
	});
}

module.exports = press_agent_manager_event_handler;
