import sys
import os

# Add the parent directory to the path so we can import from 'backend'
# This ensures that 'backend.server' is importable.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.server import app as application

# Vercel needs the app object to be named 'app'
app = application
