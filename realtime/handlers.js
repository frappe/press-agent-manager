function press_base_event_handler(socket) {
	console.log("press_base_event_handler registered");
	socket.on("hello_chat", () => {
		socket.emit("hello_chat_response", "hello world!");
		console.log("hello_chat event received");
	});
}

module.exports = press_base_event_handler;
