// InfoBridge JavaScript - Input Capture and Search Functionality

// Wait for the page to load
document.addEventListener('DOMContentLoaded', function() {
    // Get references to the input elements
    const searchInput = document.querySelector('.circular-input');
    const searchButton = document.querySelector('.search-btn');
    
    // Function to capture and process the input
    function captureUserInput() {
        // Get the text from the input box
        const userInput = searchInput.value.trim();
        
        // Check if input is not empty
        if (userInput === '') {
            alert('Please type something in the search box!');
            return;
        }
        
        // Log the captured input to console (for testing)
        console.log('User typed:', userInput);
        
        // Display what the user typed
        displayCapturedInput(userInput);
        
        
        // Clear the input box after capturing
        searchInput.value = '';
    }
    
    // Function to display the captured input
    function displayCapturedInput(input) {
        // Create or update a display area
        let displayArea = document.querySelector('.captured-input-display');
        
        if (!displayArea) {
            // Create display area if it doesn't exist
            displayArea = document.createElement('div');
            displayArea.className = 'captured-input-display card';
            
            // Insert after the main section
            const mainSection = document.querySelector('#main');
            mainSection.parentNode.insertBefore(displayArea, mainSection.nextSibling);
        }
        
        // Update the display with captured input
        displayArea.innerHTML = `
            <h3>📝 Captured Input:</h3>
            <p><strong>"${input}"</strong></p>
            <p><small>Input captured at: ${new Date().toLocaleTimeString()}</small></p>
            <button class="btn" onclick="clearDisplay()">Clear</button>
        `;
        
        // Add fade-in animation
        displayArea.style.opacity = '0';
        displayArea.style.transform = 'translateY(20px)';
        
        setTimeout(() => {
            displayArea.style.transition = 'all 0.3s ease';
            displayArea.style.opacity = '1';
            displayArea.style.transform = 'translateY(0)';
        }, 100);
    }
    
    // Function to clear the display
    window.clearDisplay = function() {
        const displayArea = document.querySelector('.captured-input-display');
        if (displayArea) {
            displayArea.style.opacity = '0';
            displayArea.style.transform = 'translateY(-20px)';
            
            setTimeout(() => {
                displayArea.remove();
            }, 300);
        }
    }
    
    // Event listeners
    if (searchButton) {
        searchButton.addEventListener('click', captureUserInput);
    }
    
    if (searchInput) {
        // Capture input when Enter key is pressed
        searchInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                captureUserInput();
            }
        });
        
        // Optional: Capture input as user types (real-time)
        searchInput.addEventListener('input', function() {
            const currentInput = searchInput.value;
            console.log('User is typing:', currentInput);
            
            // You can add real-time suggestions or validation here
        });
        
        // Focus on the input when page loads
        searchInput.focus();
    }
    
    // Additional utility functions
    
    // Function to get current input value anytime
    window.getCurrentInput = function() {
        return searchInput ? searchInput.value : '';
    }
    
    // Function to set input value programmatically
    window.setInputValue = function(value) {
        if (searchInput) {
            searchInput.value = value;
        }
    }
    
    // Function to clear input
    window.clearInput = function() {
        if (searchInput) {
            searchInput.value = '';
            searchInput.focus();
        }
    }
    
    console.log('InfoBridge input capture system loaded successfully! 🚀');
});

// Export functions for external use (if needed)
const InfoBridge = {
    getCurrentInput: () => document.querySelector('.circular-input')?.value || '',
    setInput: (value) => {
        const input = document.querySelector('.circular-input');
        if (input) input.value = value;
    },
    clearInput: () => {
        const input = document.querySelector('.circular-input');
        if (input) {
            input.value = '';
            input.focus();
        }
    }
};
