@echo off
echo.
echo 🚀 InfoBridge Gemini API Setup for Windows
echo ==========================================
echo.
echo To enable Gemini AI in InfoBridge, you need to set your API key.
echo.
echo 📋 First, get your API key from: https://makersuite.google.com/app/apikey
echo.
set /p API_KEY="📝 Enter your Gemini API key: "

if "%API_KEY%"=="" (
    echo ⏭️ No API key entered. Skipping setup.
    goto end
)

echo.
echo 🔧 Setting environment variable...
setx GEMINI_API_KEY "%API_KEY%"

if %errorlevel%==0 (
    echo ✅ API key set successfully!
    echo.
    echo 🔄 Please close and reopen your terminal/command prompt
    echo    for the environment variable to take effect.
    echo.
    echo 🚀 Then run: python infobridge_backend.py
) else (
    echo ❌ Failed to set environment variable.
    echo 💡 You can set it manually:
    echo    set GEMINI_API_KEY=%API_KEY%
)

:end
echo.
echo 📚 InfoBridge Features:
echo    • Local knowledge base (always works)  
echo    • Gemini AI (when API key is set)
echo.
pause