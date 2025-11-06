#!/usr/bin/env python3
"""List available Gemini models."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings
import google.generativeai as genai

# Configure API
genai.configure(api_key=settings.gemini_api_key)

print("Available Gemini Models:")
print("=" * 60)

for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"\n✓ {model.name}")
        print(f"  Display Name: {model.display_name}")
        print(f"  Supported Methods: {model.supported_generation_methods}")
