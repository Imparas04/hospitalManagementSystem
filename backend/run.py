"""Start the development server:  python run.py

Safe defaults: debug mode is OFF and the server listens only on this computer (127.0.0.1).
For local development you can turn debug on in .env with FLASK_DEBUG=1.
(Debug mode shows an interactive debugger in the browser - never enable it on a shared network!)
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", "5000"))
    app.run(host=host, port=port, debug=debug)
