import sys
import os

# Add the parent directory to the path so we can import from 'backend'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.server import app

# Vercel needs the app object to be named 'app'
# This file serves as the entry point for Vercel Functions.
