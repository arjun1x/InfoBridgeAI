// InfoBridge Sign-Up JavaScript
document.addEventListener('DOMContentLoaded', function() {
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
    
    // Global message elements
    const successMessage = document.getElementById('successMessage');
    const errorMessageGlobal = document.getElementById('errorMessageGlobal');

    // Real-time validation
    usernameInput.addEventListener('input', validateUsername);
    emailInput.addEventListener('input', validateEmail);
    passwordInput.addEventListener('input', validatePassword);
    confirmPasswordInput.addEventListener('input', validateConfirmPassword);
    agreeTermsCheckbox.addEventListener('change', validateTerms);

    // Form submission
    signupForm.addEventListener('submit', handleSignup);

    // Validation Functions
    function validateUsername() {
        const username = usernameInput.value.trim();
        const isValid = username.length >= 3 && username.length <= 20 && /^[a-zA-Z0-9_]+$/.test(username);
        
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

    function validateEmail() {
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

    function validatePassword() {
        const password = passwordInput.value;
        const strengthIndicator = document.getElementById('passwordStrength');
        
        if (password.length === 0) {
            showError(passwordError, '');
            strengthIndicator.textContent = '';
            return false;
        }
        
        const strength = getPasswordStrength(password);
        displayPasswordStrength(strength, strengthIndicator);
        
        if (password.length < 8) {
            showError(passwordError, 'Password must be at least 8 characters long');
            return false;
        } else if (strength.score < 2) {
            showError(passwordError, 'Password is too weak. Try adding numbers, symbols, or uppercase letters');
            return false;
        } else {
            hideError(passwordError);
            // Revalidate confirm password when password changes
            if (confirmPasswordInput.value) {
                validateConfirmPassword();
            }
            return true;
        }
    }

    function validateConfirmPassword() {
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

    function validateTerms() {
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
        let feedback = [];

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
            score: Math.max(0, Math.min(4, score)),
            feedback: feedback
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
        hideGlobalMessages();
        
        if (isSuccess) {
            successMessage.textContent = message;
            successMessage.classList.add('show');
        } else {
            errorMessageGlobal.textContent = message;
            errorMessageGlobal.classList.add('show');
        }
        
        // Auto-hide after 5 seconds
        setTimeout(hideGlobalMessages, 5000);
    }

    function hideGlobalMessages() {
        successMessage.classList.remove('show');
        errorMessageGlobal.classList.remove('show');
    }

    // Form submission handler
    async function handleSignup(event) {
        event.preventDefault();
        
        // Validate all fields
        const isUsernameValid = validateUsername();
        const isEmailValid = validateEmail();
        const isPasswordValid = validatePassword();
        const isConfirmPasswordValid = validateConfirmPassword();
        const isTermsValid = validateTerms();
        
        if (!isUsernameValid || !isEmailValid || !isPasswordValid || !isConfirmPasswordValid || !isTermsValid) {
            showGlobalMessage('Please fix the errors above before submitting', false);
            return;
        }

        // Disable submit button
        signupBtn.disabled = true;
        signupBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating Account...';

        try {
            // Prepare user data
            const userData = {
                username: usernameInput.value.trim(),
                email: emailInput.value.trim(),
                password: passwordInput.value
            };

            // Send registration request to backend
            const response = await fetch('http://localhost:5000/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(userData)
            });

            const result = await response.json();

            if (response.ok && result.success) {
                // Success
                showGlobalMessage('Account created successfully! Welcome to InfoBridge!', true);
                
                // Reset form
                signupForm.reset();
                document.getElementById('passwordStrength').textContent = '';
                
                // Redirect to login or main page after 2 seconds
                setTimeout(() => {
                    window.location.href = 'InfoBridge.html';
                }, 2000);
                
            } else {
                // Handle specific errors
                if (result.error) {
                    if (result.error.includes('username')) {
                        showError(usernameError, result.error);
                    } else if (result.error.includes('email')) {
                        showError(emailError, result.error);
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
            // Re-enable submit button
            signupBtn.disabled = false;
            signupBtn.innerHTML = '<i class="fas fa-user-plus"></i> Create Account';
        }
    }
});

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

// Utility function to check if backend is running
async function checkBackendHealth() {
    try {
        const response = await fetch('http://localhost:5000/health');
        if (response.ok) {
            console.log('✅ Backend is running');
            return true;
        }
    } catch (error) {
        console.warn('⚠️ Backend is not running. Please start the InfoBridge backend server.');
        return false;
    }
}

// Check backend on page load
checkBackendHealth();