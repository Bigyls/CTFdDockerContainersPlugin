CTFd.plugin.run((_CTFd) => {
	const $ = _CTFd.lib.$;  // Access jQuery from CTFd
	const md = _CTFd.lib.markdown();  // Access the markdown library from CTFd
});

// Get the DOM elements for the container image dropdown and its default option
var containerImage = document.getElementById("container-image");
var containerImageDefault = document.getElementById("container-image-default");

// Define the API path to fetch Docker images
var path = "/containers/api/images";

// Create a new XMLHttpRequest object to fetch the list of container images
var xhr = new XMLHttpRequest();
xhr.open("GET", path, true);  // Initialize a GET request
xhr.setRequestHeader("Accept", "application/json");  // Set the request header to accept JSON
xhr.setRequestHeader("CSRF-Token", init.csrfNonce);  // Include CSRF token for security
xhr.send();  // Send the request

// Define the function to handle the response when the request is complete
xhr.onload = function () {
	var data = JSON.parse(this.responseText);  // Parse the JSON response
	if (data.error != undefined) {
		// If there is an error in the response, display it in the default option
		containerImageDefault.innerHTML = data.error;
	} else {
		// If the response is successful, populate the dropdown with images
		for (var i = 0; i < data.images.length; i++) {
			var opt = document.createElement("option");  // Create a new option element
			opt.value = data.images[i];  // Set the option value to the image name
			opt.innerHTML = data.images[i];  // Set the displayed text of the option
			containerImage.appendChild(opt);  // Add the option to the dropdown
		}
		// Update the default option text and enable the dropdown
		containerImageDefault.innerHTML = "Choose an image...";
		containerImage.removeAttribute("disabled");
	}
	console.log(data);  // Log the response data for debugging
};
