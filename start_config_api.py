#!/usr/bin/env python3
"""
FlexiTTS Configuration API Startup Script
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and start the API
from src.api.flexitts_api import create_app
import uvicorn

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Start FlexiTTS Configuration API")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", default="info", help="Log level")
    
    args = parser.parse_args()
    
    print("=== Starting FlexiTTS Configuration API ===")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"API URL: http://{args.host}:{args.port}")
    print(f"API Docs: http://{args.host}:{args.port}/docs")
    print("==========================================")
    
    app = create_app()
    
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload
    )
