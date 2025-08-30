import os
from app101 import TwilioAIReceptionist

# Create the receptionist and get the Flask app
receptionist = TwilioAIReceptionist()
app = receptionist.app

# This ensures Flask serves on the right port
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)