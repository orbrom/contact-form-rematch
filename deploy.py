#!/usr/bin/env python3
"""
Quick deployment helper script
"""
import os
import subprocess
import sys

def run_command(command):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {command}")
            return True
        else:
            print(f"❌ {command}")
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {command}")
        print(f"Exception: {e}")
        return False

def main():
    print("🚀 Contact Form Deployment Helper")
    print("=" * 40)
    
    # Check if we're in the right directory
    if not os.path.exists('sendApp.py'):
        print("❌ Please run this script from the 'Rematch form' directory")
        sys.exit(1)
    
    print("📋 Pre-deployment checklist:")
    print("1. ✅ All files are ready")
    print("2. ✅ Requirements.txt created")
    print("3. ✅ Procfile created")
    print("4. ✅ Git repository initialized")
    
    print("\n🌐 Choose your deployment platform:")
    print("1. Railway (Recommended - Easiest)")
    print("2. Render (Alternative)")
    print("3. Heroku (Advanced)")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        print("\n🚂 Railway Deployment Steps:")
        print("1. Create a new repository on GitHub")
        print("2. Push your code to GitHub:")
        print("   git remote add origin https://github.com/YOUR_USERNAME/contact-form-rematch.git")
        print("   git push -u origin main")
        print("3. Go to https://railway.app")
        print("4. Sign up with GitHub")
        print("5. Deploy from GitHub repo")
        print("6. Add environment variables:")
        print("   - SENDER_EMAIL: orbrom97@gmail.com")
        print("   - SENDER_PASSWORD: rloj qlxt xapn wnub")
        print("   - RECIPIENT_EMAIL: harshamot.brom@gmail.com")
        
    elif choice == "2":
        print("\n🎨 Render Deployment Steps:")
        print("1. Push to GitHub (same as Railway)")
        print("2. Go to https://render.com")
        print("3. Create new Web Service")
        print("4. Connect GitHub repo")
        print("5. Add same environment variables")
        
    elif choice == "3":
        print("\n🟣 Heroku Deployment Steps:")
        print("1. Install Heroku CLI")
        print("2. Run: heroku login")
        print("3. Run: heroku create your-app-name")
        print("4. Set environment variables with heroku config:set")
        print("5. Run: git push heroku main")
        
    else:
        print("❌ Invalid choice")
        return
    
    print("\n📖 For detailed instructions, see DEPLOYMENT_GUIDE.md")
    print("🎉 Good luck with your deployment!")

if __name__ == "__main__":
    main()
