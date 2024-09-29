// Initialize challenge data and renderer
CTFd._internal.challenge.data = undefined;
CTFd._internal.challenge.renderer = null;
CTFd._internal.challenge.preRender = function () { };
CTFd._internal.challenge.render = null;
CTFd._internal.challenge.postRender = function () { };

// Function to handle submission of challenge attempts
CTFd._internal.challenge.submit = function (preview) {
	var challenge_id = parseInt(CTFd.lib.$("#challenge-id").val());
	var submission = CTFd.lib.$("#challenge-input").val();

	var body = {
		challenge_id: challenge_id,
		submission: submission,
	};
	var params = {};
	if (preview) {
		params["preview"] = true;
	}

	return CTFd.api
		.post_challenge_attempt(params, body)
		.then(function (response) {
			// Handle different response statuses
			if (response.status === 429) {
				return response; // Rate limit reached
			}
			if (response.status === 403) {
				return response; // User not logged in or CTF paused
			}
			return response; // Success or other statuses
		});
};

// Function to merge query parameters
function mergeQueryParams(parameters, queryParameters) {
	if (parameters.$queryParameters) {
		Object.keys(parameters.$queryParameters).forEach(function (parameterName) {
			var parameter = parameters.$queryParameters[parameterName];
			queryParameters[parameterName] = parameter; // Merge query parameters
		});
	}
	return queryParameters;
}

// Function to check if the container is already running
function container_running(challenge_id) {
	var path = "/containers/api/running";
	var requestButton = document.getElementById("container-request-btn");
	var requestError = document.getElementById("container-request-error");

	var xhr = new XMLHttpRequest();
	xhr.open("POST", path, true);
	xhr.setRequestHeader("Content-Type", "application/json");
	xhr.setRequestHeader("Accept", "application/json");
	xhr.setRequestHeader("CSRF-Token", init.csrfNonce);
	xhr.send(JSON.stringify({ chal_id: challenge_id }));

	xhr.onload = function () {
		var data = JSON.parse(this.responseText);
		if (data.error !== undefined) {
			// Container error handling
			requestError.style.display = "";
			requestError.firstElementChild.innerHTML = data.error;
			requestButton.removeAttribute("disabled");
		} else if (data.message !== undefined) {
			// CTFd error handling
			requestError.style.display = "";
			requestError.firstElementChild.innerHTML = data.message;
			requestButton.removeAttribute("disabled");
		} else if (data && data.status === "already_running" && data.container_id == challenge_id) {
			// If the container is already running
			console.log(challenge_id);
			container_request(challenge_id); // Request to run the container
		} else {
			// Other cases, if needed
		}
		console.log(data);
	};
}

// Function to request a new container instance
function container_request(challenge_id) {
	var path = "/containers/api/request";
	var requestButton = document.getElementById("container-request-btn");
	var requestResult = document.getElementById("container-request-result");
	var connectionInfo = document.getElementById("container-connection-info");
	var containerExpires = document.getElementById("container-expires");
	var containerExpiresTime = document.getElementById("container-expires-time");
	var requestError = document.getElementById("container-request-error");

	requestButton.setAttribute("disabled", "disabled");

	var xhr = new XMLHttpRequest();
	xhr.open("POST", path, true);
	xhr.setRequestHeader("Content-Type", "application/json");
	xhr.setRequestHeader("Accept", "application/json");
	xhr.setRequestHeader("CSRF-Token", init.csrfNonce);
	xhr.send(JSON.stringify({ chal_id: challenge_id }));

	xhr.onload = function () {
		var data = JSON.parse(this.responseText);
		if (data.error !== undefined) {
			// Handle container error
			requestError.style.display = "";
			requestError.firstElementChild.innerHTML = data.error;
			requestButton.removeAttribute("disabled");
		} else if (data.message !== undefined) {
			// Handle CTFd error
			requestError.style.display = "";
			requestError.firstElementChild.innerHTML = data.message;
			requestButton.removeAttribute("disabled");
		} else {
			// Success case
			requestError.style.display = "none";
			requestError.firstElementChild.innerHTML = "";
			requestButton.parentNode.removeChild(requestButton);
			if (data.hostname.startsWith("http")) {
				connectionInfo.innerHTML = '<a href="' + data.hostname + ':' + data.port + '" target="_blank">' + data.hostname + ':' + data.port + '</a>';
			} else {
				connectionInfo.innerHTML = data.hostname + ' ' + data.port;
			}
			containerExpires.innerHTML = Math.ceil((new Date(data.expires * 1000) - new Date()) / 1000 / 60);
			containerExpiresTime.style.display = "";
			requestResult.style.display = "";
		}
		console.log(data);
	};
}

// Function to reset the container
function container_reset(challenge_id) {
	var path = "/containers/api/reset";
	var resetButton = document.getElementById("container-reset-btn");
	var requestResult = document.getElementById("container-request-result");
	var connectionInfo = document.getElementById("container-connection-info");
	var requestError = document.getElementById("container-request-error");

	resetButton.setAttribute("disabled", "disabled");

	var xhr = new XMLHttpRequest();
	xhr.open("POST", path, true);
	xhr.setRequestHeader("Content-Type", "application/json");
	xhr.setRequestHeader("Accept", "application/json");
	xhr.setRequestHeader("CSRF-Token", init.csrfNonce);
	xhr.send(JSON.stringify({ chal_id: challenge_id }));

	xhr.onload = function () {
		var data = JSON.parse(this.responseText);
		if (data.error !== undefined) {
			// Handle container error
			requestError.style.display = "";
			requestError.firstElementChild.innerHTML = data.error;
			resetButton.removeAttribute("disabled");
		} else if (data.message !== undefined) {
			// Handle CTFd error
			requestError.style.display = "";
			requestError.firstElementChild.innerHTML = data.message;
			resetButton.removeAttribute("disabled");
		} else {
			// Success case
			requestError.style.display = "none";
			connectionInfo.innerHTML = data.hostname + ":" + data.port;
			containerExpires.innerHTML = Math.ceil((new Date(data.expires * 1000) - new Date()) / 1000 / 60);
			requestResult.style.display = "";
			resetButton.removeAttribute("disabled");
		}
		console.log(data);
	};
}

// Function to renew the container instance
function container_renew(challenge_id) {
	var path = "/containers/api/renew";
	var renewButton = document.getElementById("container-renew-btn");
	var requestResult = document.getElementById("container-request-result");
	var containerExpires = document.getElementById("container-expires");
	var requestError = document.getElementById("container-request-error");

	renewButton.setAttribute("disabled", "disabled");

	var xhr = new XMLHttpRequest();
	xhr.open("POST", path, true);
	xhr.setRequestHeader("Content-Type", "application/json");
	xhr.setRequestHeader("Accept", "application/json");
	xhr.setRequestHeader("CSRF-Token", init.csrfNonce);
	xhr.send(JSON.stringify({ chal_id: challenge_id }));

	xhr.onload = function () {
		var data = JSON.parse(this.responseText);
		if (data.error !== undefined) {
			// Handle container error
			requestError.style.display = "";
			requestError.firstElementChild.innerHTML = data.error;
			renewButton.removeAttribute("disabled");
		} else if (data.message !== undefined) {
			// Handle CTFd error
			requestError.style.display = "";
			requestError.firstElementChild.innerHTML = data.message;
			renewButton.removeAttribute("disabled");
		} else {
			// Success case
			requestError.style.display = "none";
			requestResult.style.display = "";
			containerExpires.innerHTML = Math.ceil((new Date(data.expires * 1000) - new Date()) / 1000 / 60);
			renewButton.removeAttribute("disabled");
		}
		console.log(data);
	};
}

// Function to stop the container instance
function container_stop(challenge_id) {
	var path = "/containers/api/stop";
	var stopButton = document.getElementById("container-stop-btn");
	var requestResult = document.getElementById("container-request-result");
	var connectionInfo = document.getElementById("container-connection-info");
	var requestError = document.getElementById("container-request-error");
	var containerExpiresTime = document.getElementById("container-expires-time");

	stopButton.setAttribute("disabled", "disabled");

	var xhr = new XMLHttpRequest();
	xhr.open("POST", path, true);
	xhr.setRequestHeader("Content-Type", "application/json");
	xhr.setRequestHeader("Accept", "application/json");
	xhr.setRequestHeader("CSRF-Token", init.csrfNonce);
	xhr.send(JSON.stringify({ chal_id: challenge_id }));

	xhr.onload = function () {
		var data = JSON.parse(this.responseText);
		if (data.error !== undefined) {
			// Handle container error
			requestError.style.display = "";
			requestError.firstElementChild.innerHTML = data.error;
			stopButton.removeAttribute("disabled");
		} else if (data.message !== undefined) {
			// Handle CTFd error
			requestError.style.display = "";
			requestError.firstElementChild.innerHTML = data.message;
			stopButton.removeAttribute("disabled");
		} else {
			// Success case
			requestError.style.display = "none";
			requestResult.innerHTML = "Container stopped. <br>Reopen this challenge to start another.";
			containerExpiresTime.style.display = "none"; // Hide expiration time
		}
		console.log(data);
	};
}
