document.addEventListener("DOMContentLoaded", function() {
    // Show the popup message
    function showPopupMessage(message, type = 'success') {
        var popup = document.getElementById("popup-message");
        var popupContent = document.getElementById("popup-content");
        popupContent.innerText = message;
        popup.style.display = "block";
        
        // Set the popup background color based on message type
        if (type === 'error') {
            popup.style.backgroundColor = "#dc3545"; // Red for error
        } else {
            popup.style.backgroundColor = "#28a745"; // Green for success
        }

        // Close after 5 seconds
        setTimeout(function() {
            popup.style.display = "none";
        }, 5000);
    }

    // Close the popup manually when user clicks the close button
    document.getElementById("popup-close").addEventListener("click", function() {
        document.getElementById("popup-message").style.display = "none";
    });

    // If there is an error message passed from Flask (using Jinja2)
    var errorMessage = document.getElementById("error-message").innerText;
    if (errorMessage) {
        showPopupMessage(errorMessage, 'error');  // Show error pop-up with 'error' type
    }
});
