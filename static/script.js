document.addEventListener("DOMContentLoaded", function () {
    const chatBox = document.getElementById("chat-box");
    const messageInput = document.getElementById("message-input");
    const sendButton = document.getElementById("send-button");
    const recordButton = document.getElementById("record-button");
    const loadingIndicator = document.getElementById("loading-indicator");

    let isRecording = false;
    let finalTranscript = '';
    let recognition;

    // Initialize Speech Recognition API (Web Speech API)
    if (window.SpeechRecognition || window.webkitSpeechRecognition) {
        recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.continuous = true;  // Allow continuous speech input
        recognition.interimResults = true;  // Capture interim results
        recognition.lang = 'en-US';  // Set language
    } else {
        console.log("Speech Recognition API not supported in this browser.");
        return;  // Exit if not supported
    }

    // Show loading indicator
    function showLoadingIndicator() {
        loadingIndicator.style.display = "block";
    }

    // Hide loading indicator
    function hideLoadingIndicator() {
        loadingIndicator.style.display = "none";
    }

    // Append user or AI message to chat
    function appendMessage(text, sender) {
        const messageContainer = document.createElement("div");
        messageContainer.classList.add("message-container");

        const messageDiv = document.createElement("div");
        messageDiv.classList.add("message");
        messageDiv.classList.add(sender === "User" ? "user-message" : "bot-message");
        messageDiv.textContent = text;
        messageContainer.appendChild(messageDiv);

        chatBox.appendChild(messageContainer);
        chatBox.scrollTop = chatBox.scrollHeight;

        return messageContainer;
    }

    // Send the transcribed text to the AI and get the AI's reply
function sendToAI(userInput) {
    // Append a temporary bot message saying "${personName} is thinking..."
    const thinkingMessage = `${personName} is thinking...`;
    const tempBotMessage = appendMessage(thinkingMessage, "Bot");

    // Ensure that personName is accessible
    fetch("/send_message", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            message: userInput,
            name: personName // Include personName in the payload
        }),
    })
    .then((response) => response.json())
    .then((data) => {
        // Remove the temporary "thinking" message
        tempBotMessage.remove();

        // Append the actual AI response
        appendMessage(data.response, "Bot");

        // Play AI's audio response automatically
        const audio = new Audio(data.audio_url);
        audio.play();
    })
    .catch((error) => {
        console.error("Error:", error);
        // In case of error, remove the "thinking" message
        tempBotMessage.remove();
        appendMessage("An error occurred. Please try again.", "Bot");
    });
}
    

    // Record button click event (to start/stop speech-to-text recognition)
    recordButton.addEventListener("click", function () {
        if (!isRecording) {
            // Start recording (Speech recognition)
            isRecording = true;
            recordButton.textContent = "Stop Recording";
            recordButton.classList.add("recording");

            finalTranscript = '';  // Reset final transcript
            recognition.start();  // Start speech recognition
            showLoadingIndicator();

            console.log("Speech recognition started.");

            // Capture interim and final results
            recognition.onresult = (event) => {
                let interimTranscript = '';
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript;  // Append final result
                    } else {
                        interimTranscript += event.results[i][0].transcript;  // Interim results
                    }
                }

                // Show interim transcript in the input box while speaking
                messageInput.value = interimTranscript || finalTranscript;

                console.log("Interim Transcript:", interimTranscript);
                console.log("Final Transcript (so far):", finalTranscript);
            };

            // Error handler
            recognition.onerror = (event) => {
                console.error("Speech recognition error:", event.error);
                hideLoadingIndicator();
            };

        } else {
            // Stop recording (Speech recognition)
            isRecording = false;
            recordButton.textContent = "Record";
            recordButton.classList.remove("recording");

            console.log("Stopping speech recognition...");

            // Stop recognition
            recognition.stop();
            hideLoadingIndicator();

            // Ensure any final results are captured after stopping
            recognition.onend = function () {
                console.log("Speech recognition ended.");
                console.log("Final Transcript:", finalTranscript);

                if (finalTranscript.trim() !== "") {
                    appendMessage(finalTranscript, "User");
                    sendToAI(finalTranscript);
                } else {
                    console.error("No final transcript available. Try speaking longer or more clearly.");
                }

                // Clear the input box after sending
                messageInput.value = '';
            };
        }
    });

    // Send button click event (for typed messages)
    sendButton.addEventListener("click", function () {
        const userMessage = messageInput.value;
        console.log(`Sending message to ${personName}: ${userMessage}`);
        if (userMessage.trim() === "") return;

        appendMessage(userMessage, "User");
        messageInput.value = "";

        sendToAI(userMessage);
    });

    // Allow sending messages by pressing "Enter" key
    messageInput.addEventListener("keypress", function (e) {
        if (e.key === "Enter") {
            sendButton.click();
        }
    });
});
