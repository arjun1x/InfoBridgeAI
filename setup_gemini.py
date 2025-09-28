# InfoBridge Gemini API Setup Helper
import os
import sys

def setup_gemini_api():
    """Helper script to set up Gemini API key"""
    
    print("🚀 InfoBridge Gemini API Setup")
    print("=" * 40)
    print()
    print("To enable Gemini AI in InfoBridge, you need a Gemini API key.")
    print()
    print("📋 Steps to get your API key:")
    print("1. Go to: https://makersuite.google.com/app/apikey")
    print("2. Sign in with your Google account")
    print("3. Click 'Create API Key'")
    print("4. Copy the generated API key")
    print()
    
    # Get API key from user
    api_key = input("📝 Enter your Gemini API key (or press Enter to skip): ").strip()
    
    if api_key:
        # Create a .env file for the API key
        env_content = f"GEMINI_API_KEY={api_key}\n"
        
        with open('.env', 'w') as f:
            f.write(env_content)
        
        print("✅ API key saved to .env file!")
        print()
        print("🔧 To use the API key, you can either:")
        print("1. Set environment variable: set GEMINI_API_KEY=your-api-key")
        print("2. Or modify infobridge_backend.py to load from .env file")
        print()
        
        # Show how to load from .env
        print("💡 To automatically load from .env file, add this to your backend:")
        print("from dotenv import load_dotenv")
        print("load_dotenv()  # Add this before genai.configure()")
        print()
        print("📦 Install python-dotenv: pip install python-dotenv")
        
    else:
        print("⏭️ Skipped API key setup.")
        print("💡 You can run this script again later to set up Gemini AI.")
    
    print()
    print("🎯 InfoBridge will work with:")
    print("   • Local knowledge base (always available)")
    print("   • Gemini AI (when API key is configured)")
    print()
    print("🚀 Start your backend with: python infobridge_backend.py")

if __name__ == "__main__":
    setup_gemini_api()