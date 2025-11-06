"""Example usage script for testing the backend."""

import asyncio
import httpx


async def test_chat_completion():
    """Test basic chat completion."""
    
    url = "http://localhost:8000/v1/chat/completions"
    
    payload = {
        "model": "gemini-1.5-pro",
        "messages": [
            {
                "role": "system",
                "content": "You are Aria, a cheerful and helpful AI assistant with a passion for helping people learn."
            },
            {
                "role": "user",
                "content": "Hello! What's your name?"
            }
        ],
        "temperature": 0.9,
        "max_tokens": 500,
        "stream": False,
        "user": "example_chat_123"  # Chat ID for session management
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Sending chat completion request...")
        response = await client.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print("\n✅ Success!")
            print(f"\nAssistant: {data['choices'][0]['message']['content']}")
            print(f"\nTokens used: {data['usage']['total_tokens']}")
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(response.text)


async def test_streaming():
    """Test streaming chat completion."""
    
    url = "http://localhost:8000/v1/chat/completions"
    
    payload = {
        "model": "gemini-1.5-pro",
        "messages": [
            {
                "role": "user",
                "content": "Tell me a short story about a cat."
            }
        ],
        "stream": True,
        "user": "example_chat_123"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Starting streaming request...")
        print("\nAssistant: ", end="", flush=True)
        
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix
                    
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        import json
                        chunk = json.loads(data_str)
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            print(content, end="", flush=True)
                    except:
                        pass
        
        print("\n\n✅ Streaming complete!")


async def test_multi_turn_conversation():
    """Test multi-turn conversation with memory."""
    
    url = "http://localhost:8000/v1/chat/completions"
    chat_id = "multi_turn_test"
    
    conversation = [
        "Hi! My name is Alice and I love reading fantasy books.",
        "What's your favorite genre?",
        "Can you remember my name?",  # Test memory
        "What did I say I like?"  # Test RAG retrieval
    ]
    
    messages = [
        {
            "role": "system",
            "content": "You are a friendly librarian AI who loves discussing books."
        }
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, user_msg in enumerate(conversation):
            print(f"\n--- Turn {i+1} ---")
            print(f"User: {user_msg}")
            
            # Add user message
            messages.append({
                "role": "user",
                "content": user_msg
            })
            
            # Send request
            payload = {
                "model": "gemini-1.5-pro",
                "messages": messages,
                "temperature": 0.9,
                "stream": False,
                "user": chat_id
            }
            
            response = await client.post(url, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                assistant_msg = data['choices'][0]['message']['content']
                print(f"Assistant: {assistant_msg}")
                
                # Add assistant response to conversation
                messages.append({
                    "role": "assistant",
                    "content": assistant_msg
                })
            else:
                print(f"Error: {response.status_code}")
                break
            
            # Brief pause between turns
            await asyncio.sleep(1)
    
    print("\n✅ Multi-turn conversation complete!")


async def test_health():
    """Test health endpoint."""
    
    url = "http://localhost:8000/health"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        
        if response.status_code == 200:
            data = response.json()
            print("\n🏥 Health Check:")
            print(f"  Status: {data['status']}")
            print(f"  Gemini API: {'✅' if data['gemini_api'] else '❌'}")
            print(f"  Database: {'✅' if data['database'] else '❌'}")
            print(f"  Active Sessions: {data['memory_sessions']}")
        else:
            print(f"❌ Health check failed: {response.status_code}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Emotional RAG Backend - Example Usage")
    print("=" * 60)
    
    # Test health first
    await test_health()
    
    # Test basic chat
    print("\n" + "=" * 60)
    print("Test 1: Basic Chat Completion")
    print("=" * 60)
    await test_chat_completion()
    
    # Test multi-turn
    print("\n" + "=" * 60)
    print("Test 2: Multi-Turn Conversation with Memory")
    print("=" * 60)
    await test_multi_turn_conversation()
    
    # Test streaming
    print("\n" + "=" * 60)
    print("Test 3: Streaming Response")
    print("=" * 60)
    await test_streaming()
    
    print("\n" + "=" * 60)
    print("All tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
