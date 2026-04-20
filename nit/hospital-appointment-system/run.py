# ============================================================
# Application Entry Point
# Run this file to start the Flask development server
# ============================================================

import os

from app.factory import create_app

app = create_app('development')
port = int(os.environ.get('PORT', 5001))

if __name__ == '__main__':
    print("=" * 60)
    print("  AI-Based Hospital Appointment Scheduling System")
    print("  Starting development server...")
    print(f"  URL: http://localhost:{port}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=True)
