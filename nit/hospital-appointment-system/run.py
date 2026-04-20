# ============================================================
# Application Entry Point
# Run this file to start the Flask development server
# ============================================================

import os

from app.factory import create_app
from config import config_map

# Resolve config from environment (Render should use APP_ENV=production).
config_name = os.environ.get('APP_ENV', os.environ.get('FLASK_ENV', 'development')).lower()
if config_name not in config_map:
    config_name = 'development'

app = create_app(config_name)
port = int(os.environ.get('PORT', 5001))

if __name__ == '__main__':
    print("=" * 60)
    print("  AI-Based Hospital Appointment Scheduling System")
    print(f"  Starting {config_name} server...")
    print(f"  URL: http://localhost:{port}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=(config_name == 'development'))
