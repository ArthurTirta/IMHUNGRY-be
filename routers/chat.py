import os
import uuid
import googleapiclient.discovery
import googleapiclient.errors
from fastapi import APIRouter, Depends, HTTPException
from schemas.chat import ChatMessageRequest, ChatMessageResponse, ChatHistoryItem, MessageEntry
from core.security import get_current_user
from dotenv import load_dotenv
from google.genai import types
from google import genai

load_dotenv()

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
def send_message(payload: ChatMessageRequest,current_user: dict = Depends(get_current_user)):

    def handle_tool_calls(function_calls):
        """Handle function calls from Gemini API"""
        results = []
        for function_call in function_calls:
            tool_name = function_call.name
            arguments = dict(function_call.args)
            print(f"🔨 Tool called: {tool_name} with args: {arguments}", flush=True)
            
            tool = globals().get(tool_name)
            result = tool(**arguments) if tool else {"error": "Function not found"}
            print(f"📊 Tool result: {result}", flush=True)
            
            function_response = types.FunctionResponse(
                name=tool_name,
                response={"result": result}
            )
            
            results.append(function_response)
        
        return results
    set_youtube_search_declaration = {
        "name": "set_youtube_search",
        "description": "Search YouTube for a video.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The query to search for on YouTube",
                },
            },
            "required": ["query"],
        },
    }

    def set_youtube_search(query: str):
        """
        Test endpoint: cari video YouTube berdasarkan query.
        Menggunakan YOUTUBE_API key dari .env.
        """
        api_key = os.getenv("YOUTUBE_API")
        if not api_key:
            raise HTTPException(status_code=500, detail="YOUTUBE_API key tidak ditemukan di environment")

        try:
            youtube = googleapiclient.discovery.build(
                "youtube", "v3", developerKey=api_key
            )
            response = youtube.search().list(
                part="snippet",
                q=query,
                maxResults=5,
                type="video",
            ).execute()

            results = [
                {
                    "video_id": item["id"]["videoId"],
                    "title": item["snippet"]["title"],
                    "channel": item["snippet"]["channelTitle"],
                    "description": item["snippet"]["description"],
                    "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
                    "published_at": item["snippet"]["publishedAt"],
                }
                for item in response.get("items", [])
            ]
            return {"query": query, "total_results": len(results), "items": results}

        except googleapiclient.errors.HttpError as e:
            raise HTTPException(status_code=e.status_code, detail=str(e))

    system_prompt = """You are a helpful assistant that can search YouTube for videos."""

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    tools = types.Tool(function_declarations=[set_youtube_search_declaration])
    config = types.GenerateContentConfig(tools=[tools], system_instruction=system_prompt )

    # contents = [
    #     types.Content(
    #         role="user", parts=[types.Part(text=payload.message)]
    #     )
    # ]

    # response = client.models.generate_content(
    #     model="gemini-3.5-flash",
    #     contents=contents,
    #     config=config,
    # )


    final_text = {}  # Reset final_text untuk setiap request
    
    try:
        if not payload.message:
            raise HTTPException(status_code=400, detail='Message is required')
            
        user_message = payload.message
        
        # Include user location in context
        context_message = user_message
        print(f"📩 Received message: {user_message}")
        
        history = [types.Content(role="user", parts=[types.Part(text=context_message)])]
        
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            config=config,
            contents=history
        )
        
        max_iterations = 5
        iteration_count = 0
        done = False
        
        while not done and iteration_count < max_iterations:
            iteration_count += 1
            
            if not response.candidates or len(response.candidates) == 0:
                break
            
            model_content = response.candidates[0].content
            history.append(model_content)

            # Check for function calls
            function_calls = []
            for part in model_content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    function_calls.append(part.function_call)
            
            if function_calls:
                print(f"🔧 Iteration {iteration_count}: Executing {len(function_calls)} function call(s)")
                
                function_responses = handle_tool_calls(function_calls)

                response_content = types.Content(
                    role="user",
                    parts=[types.Part(function_response=fr) for fr in function_responses]
                )
                history.append(response_content)
                
                # Send the updated history back to the model
                response = client.models.generate_content(
                    model="gemini-3-flash-preview",         
                    config=config,
                    contents=history
                )
            else:
                done = True
        
        # Extract final text response
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    final_text["response"] = part.text
                    break
        
        # Prepare response
        response_text = final_text.get("response")
        response_buttons = final_text.get("buttons")
        
        # FALLBACK: If buttons exist but no text, create default text
        if response_buttons and not response_text:
            response_text = "Here are some options for you:"
            print("⚠️ Warning: AI provided buttons without text response. Using fallback.")
        
        # Log final response
        print(f"✅ Final response:")
        print(f"   Text: {response_text[:100] if response_text else 'None'}...")
        print(f"   Buttons: {len(response_buttons) if response_buttons else 0}")
        
        session_id = payload.session_id or uuid.uuid4()
        return ChatMessageResponse(
            session_id=session_id,
            messages=[MessageEntry(question=user_message, answer={"response": response_text})]
        )
        
    except Exception as e:
        print(f"❌ Error in get_response: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f'Internal server error: {str(e)}')
    finally:
        _db_session = None
        final_text = {}  # Reset after response









@router.get("/history/{user_id}", response_model=list[ChatHistoryItem])
def get_chat_history(
    user_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Ambil daftar sesi chat milik user (untuk sidebar history).
    """
    raise NotImplementedError("Chat history belum diimplementasi")
