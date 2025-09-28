// InfoBridge JavaScript - Input Capture and Search Functionality

// Wait for the page to load
document.addEventListener('DOMContentLoaded', function() {
    // Get references to the input elements
    const searchInput = document.querySelector('.circular-input');
    const searchButton = document.querySelector('.search-btn');
    
    // Function to capture and process the input
    async function captureUserInput() {
        // Get the text from the input box
        const userInput = searchInput.value.trim();
        
        // Check if input is not empty
        if (userInput === '') {
            alert('Please type something in the search box!');
            return;
        }
        
        // Log the captured input to console (for testing)
        console.log('User typed:', userInput);
        
        // Show loading state
        showLoadingState();
        
        try {
            // Send to Python backend for processing
            const response = await searchWithBackend(userInput);
            
            if (response.success) {
                displaySearchResult(userInput, response.answer, response.source);
            } else {
                displaySearchResult(userInput, 'Error: ' + response.error, 'Error');
            }
        } catch (error) {
            console.error('Search error:', error);
            displaySearchResult(userInput, 'Sorry, there was an error connecting to the backend. Please make sure the Python server is running.', 'Connection Error');
        }
        
        // Clear the input box after capturing
        searchInput.value = '';
    }
    
    // Function to send search query to Python backend
    async function searchWithBackend(query) {
        const response = await fetch('http://localhost:5000/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: query })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    }
    
    // Function to show loading state
    function showLoadingState() {
        let displayArea = document.querySelector('.captured-input-display');
        
        if (!displayArea) {
            displayArea = document.createElement('div');
            displayArea.className = 'captured-input-display card';
            const mainSection = document.querySelector('#main');
            mainSection.parentNode.insertBefore(displayArea, mainSection.nextSibling);
        }
        
        displayArea.innerHTML = `
            <h3>🔍 Searching...</h3>
            <p>Please wait while I find information for you...</p>
            <div class="loading-spinner">⏳</div>
        `;
    }
    
    // Function to display search results
    function displaySearchResult(query, answer, source) {
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
        
        // Update the display with search results
        displayArea.innerHTML = `
            <h3>🔍 InfoBridge Search Results</h3>
            <div class="search-query">
                <strong>Your Question:</strong> "${query}"
            </div>
            <div class="search-answer">
                <strong>Answer:</strong> ${answer}
            </div>
            <div class="search-meta">
                <small>Source: ${source} | ${new Date().toLocaleTimeString()}</small>
            </div>
            <button class="btn" onclick="clearDisplay()">🔄 New Search</button>
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

// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Add glow effect to cards on hover
document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('mouseenter', function() {
        this.classList.add('glow');
    });
    card.addEventListener('mouseleave', function() {
        if (!this.classList.contains('glow')) {
            this.classList.remove('glow');
        }
    });
});
