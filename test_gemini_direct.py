#!/usr/bin/env python3
"""Direct test of Gemini API to debug response structure."""

import asyncio
import os
import sys

# Add app to path to use config
sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import settings
import google.generativeai as genai

async def test_gemini():
    """Test Gemini API and print response structure."""
    
    api_key = settings.gemini_api_key
    # Try with gemini-1.5-pro instead
    model_name = "gemini-1.5-pro"
    
    print(f"API Key: {api_key[:20]}..." if api_key else "No API key!")
    print(f"Model: {model_name}")
    print("-" * 50)
    
    # Configure API
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    print("Sending request to Gemini...")
    
    try:
        # Test request
        response = await model.generate_content_async(
            "Test",
            generation_config={"max_output_tokens": 100}
        )
        
        print(f"\n✓ Response received!")
        print(f"Type: {type(response)}")
        print(f"Dir: {[attr for attr in dir(response) if not attr.startswith('_')]}")
        
        # Check prompt feedback
        if hasattr(response, 'prompt_feedback'):
            print(f"\nPrompt Feedback: {response.prompt_feedback}")
        
        # Check candidates
        print(f"\nHas candidates: {hasattr(response, 'candidates')}")
        if hasattr(response, 'candidates'):
            print(f"Candidates: {response.candidates}")
            print(f"Number of candidates: {len(response.candidates) if response.candidates else 0}")
            
            if response.candidates:
                candidate = response.candidates[0]
                print(f"\nFirst candidate:")
                print(f"  Type: {type(candidate)}")
                print(f"  Finish reason: {getattr(candidate, 'finish_reason', 'N/A')}")
                print(f"  Safety ratings: {getattr(candidate, 'safety_ratings', 'N/A')}")
                print(f"  Has content: {hasattr(candidate, 'content')}")
                
                if hasattr(candidate, 'content'):
                    print(f"\n  Content: {candidate.content}")
                    print(f"  Content type: {type(candidate.content)}")
                    if hasattr(candidate.content, 'parts'):
                        print(f"  Parts: {candidate.content.parts}")
                        if candidate.content.parts:
                            print(f"  First part: {candidate.content.parts[0]}")
        
        # Try to access text
        print("\n" + "=" * 50)
        print("Trying to access .text attribute...")
        try:
            text = response.text
            print(f"✓ Success! Text: '{text}'")
        except Exception as e:
            print(f"✗ Failed: {type(e).__name__}: {e}")
        
        print("\n" + "=" * 50)
        print("DONE")
        
    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_gemini())
