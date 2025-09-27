@echo off
echo Pushing InfoBridge to GitHub...
cd /d "c:\Users\arjun\Downloads\Shell Hack"
git add .
git commit -m "Update InfoBridge files - latest version"
git push origin main --force
echo Done!
pause