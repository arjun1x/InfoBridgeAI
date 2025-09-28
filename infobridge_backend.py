# InfoBridge Python Backend - Enhanced with Gemini AI and User System
from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from datetime import datetime, timedelta
import google.generativeai as genai
import os
import bcrypt
import re
from pathlib import Path

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing for frontend

# Configure Gemini AI
# You'll need to get your API key from: https://makersuite.google.com/app/apikey
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', None)

# Initialize Gemini model
model = None
if GEMINI_API_KEY and GEMINI_API_KEY != 'your-gemini-api-key-here':
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        print("✅ Gemini AI initialized successfully!")
    except Exception as e:
        print(f"⚠️ Warning: Gemini AI initialization failed: {e}")
        model = None
else:
    print("⚠️ Gemini API key not configured. Using local knowledge base only.")

# User storage - Simple JSON file for demo (in production, use a proper database)
USERS_FILE = "users.json"
SESSIONS_FILE = "sessions.json"

def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def load_sessions():
    """Load sessions from JSON file"""
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_sessions(sessions):
    """Save sessions to JSON file"""
    with open(SESSIONS_FILE, 'w') as f:
        json.dump(sessions, f, indent=2)

# Initialize user storage
users_db = load_users()
sessions_db = load_sessions()

# Sample InfoBridge knowledge base
knowledge_base = {
    "what is infobridge": "InfoBridge is a smart AI assistant that acts as the bridge between your stored information and people who need it.",
    "how does it work": "InfoBridge provides quick answers to basic queries such as names, policy numbers, and key details—saving time and ensuring accuracy.",
    "version": "InfoBridge is currently version 1.0",
    "features": "InfoBridge features a black background with navy blue accents, responsive design, smooth animations, and glass morphism effects.",
    "creator": "InfoBridge was created for the Shell Hack project by arjun1x",
    "github": "You can find InfoBridge on GitHub at https://github.com/arjun1x/InfoBridgeAI",
    "technology": "InfoBridge is built with HTML, CSS, JavaScript frontend and Python Flask backend",
    "purpose": "InfoBridge helps bridge information gaps by providing quick, accurate responses to user queries",
    "help": "You can ask me about InfoBridge features, how it works, or any general questions!",
    "contact": "For support, visit the InfoBridge GitHub repository or contact through Shell Hack project"
}

@app.route('/')
def home():
    """Home endpoint - API status"""
    return jsonify({
        "message": "🚀 InfoBridge Backend API is running!",
        "version": "2.0",
        "endpoints": {
            "/search": "POST - Search for information",
            "/register": "POST - Register new user",
            "/login": "POST - User login",
            "/users": "GET - Get all users (admin)",
            "/health": "GET - Health check",
            "/knowledge": "GET - View all available topics"
        }
    })

@app.route('/search', methods=['POST'])
def search():
    """Main search endpoint with Gemini AI integration"""
    try:
        # Get JSON data from frontend
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                "success": False,
                "error": "No search query provided"
            }), 400
        
        query = data['query'].strip()
        
        if not query:
            return jsonify({
                "success": False,
                "error": "Empty search query"
            }), 400
        
        # First, check local knowledge base for InfoBridge-specific queries
        local_result = search_knowledge_base(query.lower())
        
        if local_result:
            return jsonify({
                "success": True,
                "query": data['query'],
                "answer": local_result,
                "timestamp": datetime.now().isoformat(),
                "source": "InfoBridge Knowledge Base"
            })
        
        # If not found in local knowledge base, use Gemini AI
        if model:
            try:
                gemini_response = get_gemini_response(query)
                if gemini_response:
                    return jsonify({
                        "success": True,
                        "query": data['query'],
                        "answer": gemini_response,
                        "timestamp": datetime.now().isoformat(),
                        "source": "Gemini AI"
                    })
            except Exception as gemini_error:
                print(f"Gemini API error: {gemini_error}")
                # Fall back to default response if Gemini fails
        
        # Fallback response
        suggestions = get_suggestions(query)
        return jsonify({
            "success": True,
            "query": data['query'],
            "answer": f"I don't have specific information about '{data['query']}'. {suggestions}",
            "timestamp": datetime.now().isoformat(),
            "source": "InfoBridge Default Response"
        })
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Server error: {str(e)}"
        }), 500

def get_gemini_response(query):
    """Get response from Gemini AI"""
    try:
        # Create a context-aware prompt for InfoBridge
        prompt = f"""
        You are InfoBridge, a smart AI assistant. Please provide a helpful, accurate, and concise response to the following question.
        Keep your response informative but not too lengthy - aim for 1-3 sentences unless more detail is specifically requested.
        
        Question: {query}
        
        Response:
        """
        
        # Generate response using Gemini
        response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text.strip()
        else:
            return None
            
    except Exception as e:
        print(f"Gemini API error: {e}")
        return None

def search_knowledge_base(query):
    """Search through the knowledge base"""
    query_lower = query.lower()
    
    # Direct match
    if query_lower in knowledge_base:
        return knowledge_base[query_lower]
    
    # Partial match - check if query contains any keywords
    for key, value in knowledge_base.items():
        if any(word in query_lower for word in key.split()) or any(word in key for word in query_lower.split()):
            return value
    
    # Keyword-based search
    keywords = {
        "info": "what is infobridge",
        "about": "what is infobridge", 
        "work": "how does it work",
        "function": "how does it work",
        "feature": "features",
        "tech": "technology",
        "build": "technology",
        "code": "github",
        "repository": "github",
        "repo": "github",
        "support": "contact",
        "help": "help",
        "creator": "creator",
        "author": "creator",
        "version": "version"
    }
    
    for keyword, knowledge_key in keywords.items():
        if keyword in query_lower:
            return knowledge_base.get(knowledge_key)
    
    return None

def get_suggestions(query):
    """Get suggestions for unknown queries"""
    suggestions = [
        "Try asking about 'what is InfoBridge'",
        "Ask 'how does it work'",
        "Try 'features' or 'technology'",
        "Ask about 'version' or 'creator'"
    ]
    
    return "Here are some things you can ask me: " + ", ".join(suggestions[:2])

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "message": "InfoBridge Backend is running smoothly! 🚀",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/knowledge', methods=['GET'])
def get_knowledge():
    """Get all available knowledge topics"""
    return jsonify({
        "available_topics": list(knowledge_base.keys()),
        "total_topics": len(knowledge_base),
        "message": "These are the topics I can help you with!"
    })

@app.route('/register', methods=['POST'])
def register_user():
    """User registration endpoint"""
    try:
        # Get JSON data from frontend
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No registration data provided"
            }), 400
        
        # Extract user data
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        # Validate required fields
        if not username or not email or not password:
            return jsonify({
                "success": False,
                "error": "Username, email, and password are required"
            }), 400
        
        # Validate username
        username_error = validate_username(username)
        if username_error:
            return jsonify({
                "success": False,
                "error": username_error
            }), 400
        
        # Validate email
        email_error = validate_email(email)
        if email_error:
            return jsonify({
                "success": False,
                "error": email_error
            }), 400
        
        # Validate password
        password_error = validate_password(password)
        if password_error:
            return jsonify({
                "success": False,
                "error": password_error
            }), 400
        
        # Check if username already exists
        if username in users_db:
            return jsonify({
                "success": False,
                "error": "Username already exists. Please choose a different username."
            }), 400
        
        # Check if email already exists
        for existing_user, user_data in users_db.items():
            if user_data.get('email') == email:
                return jsonify({
                    "success": False,
                    "error": "Email already registered. Please use a different email or try logging in."
                }), 400
        
        # Hash password
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Create user record
        user_record = {
            "username": username,
            "email": email,
            "password_hash": password_hash.decode('utf-8'),
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "is_active": True
        }
        
        # Save user to database
        users_db[username] = user_record
        save_users(users_db)
        
        print(f"✅ New user registered: {username} ({email})")
        
        return jsonify({
            "success": True,
            "message": "Account created successfully! Welcome to InfoBridge!",
            "user": {
                "username": username,
                "email": email,
                "created_at": user_record["created_at"]
            }
        })
        
    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({
            "success": False,
            "error": "Server error during registration. Please try again."
        }), 500

def validate_username(username):
    """Validate username format and requirements"""
    if len(username) < 3:
        return "Username must be at least 3 characters long"
    
    if len(username) > 20:
        return "Username must be no more than 20 characters long"
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return "Username can only contain letters, numbers, and underscores"
    
    return None

def validate_email(email):
    """Validate email format"""
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        return "Please enter a valid email address"
    
    return None

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return "Password must be at least 8 characters long"
    
    # Check for at least one uppercase, one lowercase, and one number
    if not re.search(r'[A-Z]', password):
        return "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return "Password must contain at least one number"
    
    return None

@app.route('/login', methods=['POST'])
def login_user():
    """User login endpoint"""
    try:
        # Get JSON data from frontend
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No login data provided"
            }), 400
        
        # Extract login data
        username_or_email = data.get('username', '').strip().lower()
        password = data.get('password', '')
        
        if not username_or_email or not password:
            return jsonify({
                "success": False,
                "error": "Username/email and password are required"
            }), 400
        
        # Find user by username or email
        user_found = None
        user_key = None
        
        for key, user_data in users_db.items():
            if (key.lower() == username_or_email or 
                user_data.get('email', '').lower() == username_or_email):
                user_found = user_data
                user_key = key
                break
        
        if not user_found:
            return jsonify({
                "success": False,
                "error": "User not found. Please check your username/email or sign up for a new account."
            }), 401
        
        # Verify password
        if not bcrypt.checkpw(password.encode('utf-8'), user_found['password_hash'].encode('utf-8')):
            return jsonify({
                "success": False,
                "error": "Incorrect password. Please try again."
            }), 401
        
        # Update last login
        users_db[user_key]['last_login'] = datetime.now().isoformat()
        save_users(users_db)
        
        print(f"✅ User logged in: {user_key} ({user_found['email']})")
        
        return jsonify({
            "success": True,
            "message": f"Welcome back, {user_key}!",
            "user": {
                "username": user_key,
                "email": user_found["email"],
                "last_login": users_db[user_key]['last_login']
            }
        })
        
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({
            "success": False,
            "error": "Server error during login. Please try again."
        }), 500

@app.route('/users', methods=['GET'])
def get_users():
    """Get all registered users (for admin purposes)"""
    user_list = []
    for username, user_data in users_db.items():
        user_list.append({
            "username": username,
            "email": user_data["email"],
            "created_at": user_data["created_at"],
            "last_login": user_data.get("last_login"),
            "is_active": user_data.get("is_active", True)
        })
    
    return jsonify({
        "success": True,
        "users": user_list,
        "total_users": len(user_list)
    })

if __name__ == '__main__':
    print("🚀 Starting InfoBridge Backend Server...")
    print("📡 Server running on: http://localhost:5000")
    print("🔍 Search endpoint: http://localhost:5000/search")
    print("👤 User registration: http://localhost:5000/register")
    print("👥 Users list: http://localhost:5000/users")
    print("❤️ Health check: http://localhost:5000/health")
    print("📚 Knowledge base: http://localhost:5000/knowledge")
    
    if model:
        print("🤖 Gemini AI: Enabled ✅")
    else:
        print("🤖 Gemini AI: Disabled (API key needed) ❌")
        print("💡 To enable Gemini AI, get your API key from: https://makersuite.google.com/app/apikey")
        print("💡 Then set environment variable: GEMINI_API_KEY=your-api-key")
    
    print(f"👤 Registered users: {len(users_db)}")
    print("=" * 50)
    
    # Run the Flask app
    app.run(host='localhost', port=5000, debug=True)