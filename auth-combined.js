// InfoBridge Combined Authentication & Main Interface JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Check if user is already logged in
    checkExistingLogin();
    
    // Initialize authentication forms
    initializeAuth();
});

// Global variables
let currentUser = null;
let isLoggedIn = false;
let currentMode = 'signup'; // 'signup' or 'login' or 'main'

// Check for existing login
function checkExistingLogin() {
    const userData = localStorage.getItem('infobridgeUser');
    if (userData) {
        try {
            currentUser = JSON.parse(userData);
            isLoggedIn = true;
            showMainInterface();
        } catch (e) {
            console.log('Invalid stored user data');
            localStorage.removeItem('infobridgeUser');
        }
    }
}

// Initialize authentication forms
function initializeAuth() {
    const signupForm = document.getElementById('signupForm');
    const loginForm = document.getElementById('loginForm');
    
    if (signupForm) {
        initializeSignup();
    }
    
    if (loginForm) {
        initializeLogin();
    }
}

// Initialize signup functionality
function initializeSignup() {
    const signupForm = document.getElementById('signupForm');
    const signupBtn = document.getElementById('signupBtn');
    
    // Form elements
    const usernameInput = document.getElementById('username');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirmPassword');
    const agreeTermsCheckbox = document.getElementById('agreeTerms');
    
    // Error message elements
    const usernameError = document.getElementById('usernameError');
    const emailError = document.getElementById('emailError');
    const passwordError = document.getElementById('passwordError');
    const confirmPasswordError = document.getElementById('confirmPasswordError');
    const termsError = document.getElementById('termsError');

    // Real-time validation
    usernameInput.addEventListener('input', () => validateUsername(usernameInput, usernameError));
    emailInput.addEventListener('input', () => validateEmail(emailInput, emailError));
    passwordInput.addEventListener('input', () => validatePassword(passwordInput, passwordError, confirmPasswordInput, confirmPasswordError));
    confirmPasswordInput.addEventListener('input', () => validateConfirmPassword(passwordInput, confirmPasswordInput, confirmPasswordError));
    agreeTermsCheckbox.addEventListener('change', () => validateTerms(agreeTermsCheckbox, termsError));

    // Form submission
    signupForm.addEventListener('submit', handleSignup);
}

// Initialize login functionality
function initializeLogin() {
    const loginForm = document.getElementById('loginForm');
    const loginBtn = document.getElementById('loginBtn');
    
    const loginUsernameInput = document.getElementById('loginUsername');
    const loginPasswordInput = document.getElementById('loginPassword');
    const loginUsernameError = document.getElementById('loginUsernameError');
    const loginPasswordError = document.getElementById('loginPasswordError');

    // Real-time validation
    loginUsernameInput.addEventListener('input', () => {
        if (loginUsernameInput.value.trim()) {
            hideError(loginUsernameError);
        }
    });
    
    loginPasswordInput.addEventListener('input', () => {
        if (loginPasswordInput.value) {
            hideError(loginPasswordError);
        }
    });

    // Form submission
    loginForm.addEventListener('submit', handleLogin);
}

// Toggle between signup and login forms
function toggleToLogin() {
    currentMode = 'login';
    document.getElementById('signupForm').style.display = 'none';
    document.getElementById('loginForm').style.display = 'block';
    document.getElementById('headerTitle').textContent = 'Welcome Back';
    document.getElementById('headerSubtitle').textContent = 'Sign in to access your AI-powered information assistant';
    clearMessages();
}

function toggleToSignup() {
    currentMode = 'signup';
    document.getElementById('signupForm').style.display = 'block';
    document.getElementById('loginForm').style.display = 'none';
    document.getElementById('headerTitle').textContent = 'Join InfoBridge';
    document.getElementById('headerSubtitle').textContent = 'Create your account to access AI-powered information assistance';
    clearMessages();
}

// Validation Functions
function validateUsername(usernameInput, usernameError) {
    const username = usernameInput.value.trim();
    
    if (username.length === 0) {
        showError(usernameError, '');
        return false;
    } else if (username.length < 3) {
        showError(usernameError, 'Username must be at least 3 characters long');
        return false;
    } else if (username.length > 20) {
        showError(usernameError, 'Username must be no more than 20 characters long');
        return false;
    } else if (!/^[a-zA-Z0-9_]+$/.test(username)) {
        showError(usernameError, 'Username can only contain letters, numbers, and underscores');
        return false;
    } else {
        hideError(usernameError);
        return true;
    }
}

function validateEmail(emailInput, emailError) {
    const email = emailInput.value.trim();
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    
    if (email.length === 0) {
        showError(emailError, '');
        return false;
    } else if (!emailRegex.test(email)) {
        showError(emailError, 'Please enter a valid email address');
        return false;
    } else {
        hideError(emailError);
        return true;
    }
}

function validatePassword(passwordInput, passwordError, confirmPasswordInput, confirmPasswordError) {
    const password = passwordInput.value;
    const strengthIndicator = document.getElementById('passwordStrength');
    
    if (password.length === 0) {
        showError(passwordError, '');
        if (strengthIndicator) strengthIndicator.textContent = '';
        return false;
    }
    
    const strength = getPasswordStrength(password);
    if (strengthIndicator) displayPasswordStrength(strength, strengthIndicator);
    
    if (password.length < 8) {
        showError(passwordError, 'Password must be at least 8 characters long');
        return false;
    } else if (strength.score < 2) {
        showError(passwordError, 'Password is too weak. Try adding numbers, symbols, or uppercase letters');
        return false;
    } else {
        hideError(passwordError);
        // Revalidate confirm password when password changes
        if (confirmPasswordInput && confirmPasswordInput.value) {
            validateConfirmPassword(passwordInput, confirmPasswordInput, confirmPasswordError);
        }
        return true;
    }
}

function validateConfirmPassword(passwordInput, confirmPasswordInput, confirmPasswordError) {
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;
    
    if (confirmPassword.length === 0) {
        showError(confirmPasswordError, '');
        return false;
    } else if (password !== confirmPassword) {
        showError(confirmPasswordError, 'Passwords do not match');
        return false;
    } else {
        hideError(confirmPasswordError);
        return true;
    }
}

function validateTerms(agreeTermsCheckbox, termsError) {
    if (!agreeTermsCheckbox.checked) {
        showError(termsError, 'You must agree to the Terms of Service and Privacy Policy');
        return false;
    } else {
        hideError(termsError);
        return true;
    }
}

// Password strength checker
function getPasswordStrength(password) {
    let score = 0;

    // Length check
    if (password.length >= 8) score++;
    if (password.length >= 12) score++;

    // Character diversity
    if (/[a-z]/.test(password)) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;

    // Common patterns (reduce score)
    if (/(.)\1{2,}/.test(password)) score--; // Repeated characters
    if (/123|abc|qwerty/i.test(password)) score--; // Common sequences

    return {
        score: Math.max(0, Math.min(4, score))
    };
}

function displayPasswordStrength(strength, element) {
    const strengthLabels = ['Very Weak', 'Weak', 'Fair', 'Strong', 'Very Strong'];
    const strengthClasses = ['very-weak', 'weak', 'medium', 'strong', 'very-strong'];
    
    element.textContent = `Password strength: ${strengthLabels[strength.score]}`;
    element.className = `password-strength ${strengthClasses[strength.score]}`;
}

// Error handling functions
function showError(errorElement, message) {
    errorElement.textContent = message;
    errorElement.classList.add('show');
}

function hideError(errorElement) {
    errorElement.textContent = '';
    errorElement.classList.remove('show');
}

function showGlobalMessage(message, isSuccess = false) {
    clearMessages();
    
    const successMessage = document.getElementById('successMessage');
    const errorMessageGlobal = document.getElementById('errorMessageGlobal');
    
    if (isSuccess && successMessage) {
        successMessage.textContent = message;
        successMessage.classList.add('show');
    } else if (errorMessageGlobal) {
        errorMessageGlobal.textContent = message;
        errorMessageGlobal.classList.add('show');
    }
    
    // Auto-hide after 5 seconds
    setTimeout(clearMessages, 5000);
}

function clearMessages() {
    const successMessage = document.getElementById('successMessage');
    const errorMessageGlobal = document.getElementById('errorMessageGlobal');
    
    if (successMessage) successMessage.classList.remove('show');
    if (errorMessageGlobal) errorMessageGlobal.classList.remove('show');
}

// Handle signup
async function handleSignup(event) {
    event.preventDefault();
    
    const usernameInput = document.getElementById('username');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirmPassword');
    const agreeTermsCheckbox = document.getElementById('agreeTerms');
    const signupBtn = document.getElementById('signupBtn');
    
    // Validate all fields
    const isUsernameValid = validateUsername(usernameInput, document.getElementById('usernameError'));
    const isEmailValid = validateEmail(emailInput, document.getElementById('emailError'));
    const isPasswordValid = validatePassword(passwordInput, document.getElementById('passwordError'), confirmPasswordInput, document.getElementById('confirmPasswordError'));
    const isConfirmPasswordValid = validateConfirmPassword(passwordInput, confirmPasswordInput, document.getElementById('confirmPasswordError'));
    const isTermsValid = validateTerms(agreeTermsCheckbox, document.getElementById('termsError'));
    
    if (!isUsernameValid || !isEmailValid || !isPasswordValid || !isConfirmPasswordValid || !isTermsValid) {
        showGlobalMessage('Please fix the errors above before submitting', false);
        return;
    }

    // Disable submit button
    signupBtn.disabled = true;
    signupBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating Account...';

    try {
        const userData = {
            username: usernameInput.value.trim(),
            email: emailInput.value.trim(),
            password: passwordInput.value
        };

        const response = await fetch('http://localhost:5001/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(userData)
        });

        const result = await response.json();

        if (response.ok && result.success) {
            // Store user info
            currentUser = {
                username: userData.username,
                email: userData.email,
                loginTime: new Date().toISOString()
            };
            localStorage.setItem('infobridgeUser', JSON.stringify(currentUser));
            isLoggedIn = true;
            
            showGlobalMessage(`🎉 Welcome to InfoBridge, ${userData.username}! Loading your AI assistant...`, true);
            
            // Transition to main interface after 2 seconds
            setTimeout(() => {
                showMainInterface();
            }, 2000);
            
        } else {
            if (result.error) {
                if (result.error.includes('username')) {
                    showError(document.getElementById('usernameError'), result.error);
                } else if (result.error.includes('email')) {
                    showError(document.getElementById('emailError'), result.error);
                } else {
                    showGlobalMessage(result.error, false);
                }
            } else {
                showGlobalMessage('Registration failed. Please try again.', false);
            }
        }

    } catch (error) {
        console.error('Registration error:', error);
        showGlobalMessage('Network error. Please check your connection and try again.', false);
    } finally {
        signupBtn.disabled = false;
        signupBtn.innerHTML = '<i class="fas fa-user-plus"></i> Create Account';
    }
}

// Handle login
async function handleLogin(event) {
    event.preventDefault();
    
    const loginUsernameInput = document.getElementById('loginUsername');
    const loginPasswordInput = document.getElementById('loginPassword');
    const loginBtn = document.getElementById('loginBtn');
    
    const username = loginUsernameInput.value.trim();
    const password = loginPasswordInput.value;
    
    if (!username) {
        showError(document.getElementById('loginUsernameError'), 'Username or email is required');
        return;
    }
    
    if (!password) {
        showError(document.getElementById('loginPasswordError'), 'Password is required');
        return;
    }

    loginBtn.disabled = true;
    loginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing In...';

    try {
        const response = await fetch('http://localhost:5001/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password })
        });

        const result = await response.json();

        if (response.ok && result.success) {
            currentUser = {
                username: result.user.username,
                email: result.user.email,
                loginTime: new Date().toISOString()
            };
            localStorage.setItem('infobridgeUser', JSON.stringify(currentUser));
            isLoggedIn = true;
            
            showGlobalMessage(`Welcome back, ${result.user.username}! Loading InfoBridge...`, true);
            
            setTimeout(() => {
                showMainInterface();
            }, 1500);
            
        } else {
            showGlobalMessage(result.error || 'Login failed. Please try again.', false);
        }

    } catch (error) {
        console.error('Login error:', error);
        showGlobalMessage('Network error. Please check your connection and try again.', false);
    } finally {
        loginBtn.disabled = false;
        loginBtn.innerHTML = '<i class="fas fa-sign-in-alt"></i> Sign In to InfoBridge';
    }
}

// Show main InfoBridge interface
function showMainInterface() {
    currentMode = 'main';
    
    // Hide auth forms
    const authContainer = document.querySelector('.signup-container');
    if (authContainer) {
        authContainer.style.display = 'none';
    }
    
    // Create main InfoBridge interface
    createMainInterface();
}

// Create the main InfoBridge interface
function createMainInterface() {
    // Load InfoBridge CSS first
    loadInfoBridgeCSS();
    
    // Wait a moment for CSS to load, then create interface
    setTimeout(() => {
        // Create main interface HTML that exactly matches InfoBridge.html
        const mainHTML = `
            <header>
                <div class="header-content">
                    <img src="InfoBridgeAI JPG.png" alt="InfoBridge AI Assistant" class="header-logo">
                    <div class="user-controls" style="position: absolute; top: 20px; right: 20px; z-index: 100;">
                        <span style="color: #64b5f6; margin-right: 15px; font-weight: bold;">Welcome, ${currentUser.username}!</span>
                        <button onclick="logout()" style="background: linear-gradient(45deg, #1a237e, #0d47a1); color: white; border: none; padding: 8px 16px; border-radius: 20px; cursor: pointer; transition: all 0.3s ease;">
                            Logout
                        </button>
                    </div>
                </div>
            </header>

            <main>
                <!-- Main Display -->
                <section id="main" class="card glow">
                    <h2 id="welcomeTitle">Welcome to InfoBridge</h2>
                    <p id="welcomeSubtitle" style="color: rgba(255, 255, 255, 0.8); margin-bottom: 20px; display: block; text-align: center;">
                        Hello ${currentUser.username}! Your account is ready. Ask me anything and I'll help you find the information you need.
                    </p>
                    <div class="input-container">
                        <input type="text" class="circular-input" placeholder="Type your question here..." id="searchInput" />
                        <button class="search-btn" id="searchBtn">🔍</button>
                    </div>
                    <div id="searchResult" style="margin-top: 20px; display: none;"></div>
                </section>
                <section id="agent-section" class="card glow" style="margin-top: 20px;">
                <h3>AI Agent Assistant</h3>
                <div style="display: flex; flex-direction: column; gap: 15px;">
                <input type="text" id="agentTaskInput" placeholder="What should the agent do? (e.g., Schedule appointment)" style="padding: 12px; border-radius: 8px; background: rgba(255,255,255,0.1); color: white; border: 1px solid rgba(255,255,255,0.3);">
                <input type="tel" id="targetPhoneInput" placeholder="Target phone number (e.g., +1234567890)" style="padding: 12px; border-radius: 8px; background: rgba(255,255,255,0.1); color: white; border: 1px solid rgba(255,255,255,0.3);">
                <button onclick="runAgentTask()" style="background: linear-gradient(45deg, #1a237e, #0d47a1); color: white; border: none; padding: 12px 24px; border-radius: 25px; cursor: pointer;">
            Start AI Agent
                    </button>
                    </div>
                <div id="agentResult" style="margin-top: 20px; display: none;"></div>
                    </section>
                
            </main>

            <footer>
                <div class="footer-content">
                    <p>&copy; 2025 InfoBridgeAI</p>
                    <p>Built with passion for innovation</p>
                </div>
            </footer>
        `;
        
        // Replace body content
        document.body.innerHTML = mainHTML;
        
        // Apply InfoBridge body styling - remove all inline styles and use CSS classes
        document.body.className = '';
        document.body.removeAttribute('style');
        
        // Add smooth entrance animation
        document.body.style.animation = 'fadeIn 0.8s ease-in-out';
        
        // Initialize search functionality
        initializeSearch();
        
        // Add pulse animation for the welcome title
        const welcomeTitle = document.getElementById('welcomeTitle');
        if (welcomeTitle) {
            welcomeTitle.style.animation = 'pulse 2s ease-in-out';
        }
        
        // Focus on search input
        setTimeout(() => {
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.focus();
            }
        }, 500);
        
    }, 100); // Small delay to ensure CSS is loaded
}

// Load InfoBridge CSS
function loadInfoBridgeCSS() {
    // Remove any existing auth styles
    const authStyle = document.querySelector('link[href="signup.css"]');
    if (authStyle) {
        authStyle.remove();
    }
    
    // Check if InfoBridge CSS is already loaded
    const existingLink = document.querySelector('link[href="InfoBridge.css"]');
    if (!existingLink) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'InfoBridge.css';
        document.head.appendChild(link);
    }
    
    // Add custom animations for smooth transitions
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
        
        .user-controls button:hover {
            background: linear-gradient(45deg, #0d47a1, #1a237e) !important;
            transform: scale(1.05);
        }
    `;
    document.head.appendChild(style);
}

// Initialize search functionality
function initializeSearch() {
    const searchInput = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const searchResult = document.getElementById('searchResult');
    
    // Search button click handler
    searchBtn.addEventListener('click', performSearch);
    
    // Enter key handler
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            performSearch();
        }
    });
    
    // Focus on input
    searchInput.focus();
    
    async function performSearch() {
        const query = searchInput.value.trim();
        
        if (!query) {
            return;
        }
        
        // Show loading state
        searchBtn.innerHTML = '⏳';
        searchBtn.disabled = true;
        searchResult.style.display = 'block';
        searchResult.innerHTML = '<p style="color: rgba(255, 255, 255, 0.7);">🔍 Searching...</p>';
        
        try {
            const response = await fetch('http://localhost:5001/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query: query })
            });
            
            const result = await response.json();
            
            if (result.success) {
                // Display result with InfoBridge styling that matches the original
                searchResult.innerHTML = `
                    <div style="background: rgba(255, 255, 255, 0.1); padding: 20px; border-radius: 15px; border-left: 4px solid #64b5f6; animation: fadeIn 0.5s ease-out;">
                        <h4 style="color: #64b5f6; margin-bottom: 10px;">Answer:</h4>
                        <p style="color: white; line-height: 1.6; margin-bottom: 15px;">${result.answer}</p>
                        <small style="color: rgba(255, 255, 255, 0.5); margin-top: 10px; display: block;">
                            Source: ${result.source} | ${new Date(result.timestamp).toLocaleTimeString()}
                        </small>
                        <button onclick="clearSearch()" style="background: linear-gradient(45deg, #1a237e, #0d47a1); color: white; border: none; padding: 8px 16px; border-radius: 20px; cursor: pointer; margin-top: 15px; transition: all 0.3s ease;">
                            🔄 New Search
                        </button>
                    </div>
                `;
            } else {
                searchResult.innerHTML = `
                    <div style="background: rgba(244, 67, 54, 0.1); padding: 20px; border-radius: 15px; border-left: 4px solid #f44336; animation: fadeIn 0.5s ease-out;">
                        <h4 style="color: #f44336; margin-bottom: 10px;">Error:</h4>
                        <p style="color: white; margin-bottom: 15px;">${result.error}</p>
                        <button onclick="clearSearch()" style="background: linear-gradient(45deg, #f44336, #d32f2f); color: white; border: none; padding: 8px 16px; border-radius: 20px; cursor: pointer; margin-top: 10px; transition: all 0.3s ease;">
                            Try Again
                        </button>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Search error:', error);
            searchResult.innerHTML = `
                <div style="background: rgba(244, 67, 54, 0.1); padding: 20px; border-radius: 15px; border-left: 4px solid #f44336; animation: fadeIn 0.5s ease-out;">
                    <h4 style="color: #f44336; margin-bottom: 10px;">Connection Error:</h4>
                    <p style="color: white; margin-bottom: 15px;">Unable to connect to InfoBridge backend. Please make sure the server is running.</p>
                    <button onclick="clearSearch()" style="background: linear-gradient(45deg, #f44336, #d32f2f); color: white; border: none; padding: 8px 16px; border-radius: 20px; cursor: pointer; margin-top: 10px; transition: all 0.3s ease;">
                        Try Again
                    </button>
                </div>
            `;
        } finally {
            searchBtn.innerHTML = '🔍';
            searchBtn.disabled = false;
        }
    }
}

// Clear search results
function clearSearch() {
    const searchResult = document.getElementById('searchResult');
    const searchInput = document.getElementById('searchInput');
    
    if (searchResult) {
        searchResult.style.display = 'none';
        searchResult.innerHTML = '';
    }
    
    if (searchInput) {
        searchInput.value = '';
        searchInput.focus();
    }
}

// Logout function
function logout() {
    localStorage.removeItem('infobridgeUser');
    currentUser = null;
    isLoggedIn = false;
    location.reload();
}

// Password visibility toggle function
function togglePassword(inputId) {
    const passwordInput = document.getElementById(inputId);
    const eyeIcon = document.getElementById(inputId + 'Eye');
    
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        eyeIcon.className = 'fas fa-eye-slash';
    } else {
        passwordInput.type = 'password';
        eyeIcon.className = 'fas fa-eye';
    }
}

// Backend health check
async function checkBackendHealth() {
    try {
        const response = await fetch('http://localhost:5001/health');
        if (response.ok) {
            console.log('✅ Backend is running');
            return true;
        }
    } catch (error) {
        console.warn('⚠️ Backend is not running. Please start the InfoBridge backend server.');
        return false;
    }
}
// Add these functions at the END of auth-combined.js
async function runAgentTask() {
    const taskInput = document.getElementById('agentTaskInput');
    const phoneInput = document.getElementById('targetPhoneInput');
    const task = taskInput.value.trim();
    const phone = phoneInput.value.trim();
    
    if (!task || !phone) {
        alert('Please enter both task and phone number');
        return;
    }
    
    const agentResult = document.getElementById('agentResult');
    agentResult.style.display = 'block';
    agentResult.innerHTML = '<p style="color: white;">🤖 Agent initiating call...</p>';
    
    try {
        const response = await fetch('http://localhost:5000/api/initiate_call', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                query: task,
                phone: phone,
                user_id: currentUser ? currentUser.username : 'guest'
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            agentResult.innerHTML = `
                <div style="background: rgba(76, 175, 80, 0.2); padding: 20px; border-radius: 15px; border-left: 4px solid #4caf50;">
                    <h4 style="color: #4caf50;">✅ Agent Call Initiated!</h4>
                    <p style="color: white;">Call SID: ${result.call_sid}</p>
                    <p style="color: white;">The agent is now calling ${phone}</p>
                    <button onclick="checkAgentStatus('${result.call_sid}')" style="margin-top: 10px; padding: 8px 16px; background: #4caf50; color: white; border: none; border-radius: 5px; cursor: pointer;">
                        Check Status
                    </button>
                </div>
            `;
        } else {
            agentResult.innerHTML = `
                <div style="background: rgba(244, 67, 54, 0.2); padding: 20px; border-radius: 15px;">
                    <p style="color: #f44336;">Error: ${result.error}</p>
                </div>
            `;
        }
    } catch (error) {
        agentResult.innerHTML = `<p style="color: #f44336;">Error: ${error.message}</p>`;
    }
}

async function checkAgentStatus(callSid) {
    try {
        const response = await fetch(`http://localhost:5001/api/call_status/${callSid}`);
        const data = await response.json();
        
        if (data.success) {
            alert(`Call Status: ${data.state}\nTranscript: ${JSON.stringify(data.transcript)}`);
        } else {
            alert('Could not get call status');
        }
    } catch (error) {
        alert('Error checking status: ' + error.message);
    }
}



// Check backend on page load
checkBackendHealth();
