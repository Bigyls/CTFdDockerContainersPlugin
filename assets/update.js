// Get references to the container image dropdown and its default option
var containerImage = document.getElementById("container-image");
var containerImageDefault = document.getElementById("container-image-default");

// Define the API endpoint to fetch Docker images
var path = "/containers/api/images";

// Create a new XMLHttpRequest object to communicate with the server
var xhr = new XMLHttpRequest();
xhr.open("GET", path, true); // Initialize a GET request to the specified path
xhr.setRequestHeader("Accept", "application/json"); // Indicate that we expect a JSON response
xhr.setRequestHeader("CSRF-Token", init.csrfNonce); // Include CSRF token for security
xhr.send(); // Send the request

// Define what happens when the request completes
xhr.onload = function () {
	var data = JSON.parse(this.responseText); // Parse the JSON response
	if (data.error != undefined) {
		// If an error is returned from the server
		containerImageDefault.innerHTML = data.error; // Display the error message in the default option
	} else {
		// If the request is successful and returns images
		for (var i = 0; i < data.images.length; i++) {
			// Loop through each image returned
			var opt = document.createElement("option"); // Create a new option element
			opt.value = data.images[i]; // Set the value of the option to the image name
			opt.innerHTML = data.images[i]; // Set the displayed text to the image name
			containerImage.appendChild(opt); // Append the option to the dropdown
		}
		containerImageDefault.innerHTML = "Choose an image..."; // Update the default option text
		containerImage.removeAttribute("disabled"); // Enable the dropdown for user selection
		containerImage.value = container_image_selected; // Set the dropdown to the currently selected image
	}
	console.log(data); // Log the response data for debugging purposes
};
