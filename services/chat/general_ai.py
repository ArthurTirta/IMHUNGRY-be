"""
General AI (orchestrator) untuk endpoint /chat/message.

Tanggung jawab:
- Menerima pesan user + konteks session
- Memanggil tool yang tepat (ai_tutorial_generator / get_recipe_by_id)
- Mengembalikan teks intro AI + recipe_id (jika ada)
"""
import os
import uuid as uuid_module

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from models.chat import Chat
from models.user import User
from schemas.chat import ChatMessageRequest, ChatMessageResponse
from services.chat.recipe_tools import handle_tool_calls, enrich_with_recipe
from services.chat.summary import update_summary

GEMINI_MODEL = "gemini-2.0-flash"

# ---------------------------------------------------------------------------
# Tool declarations
# ---------------------------------------------------------------------------

TOOL_DECLARATIONS = [
    {
        "name": "ai_tutorial_generator",
        "description": (
            "Gunakan tool ini ketika user meminta resep, tutorial memasak, atau cara membuat "
            "makanan/minuman tertentu. Tool ini akan mencari video YouTube yang relevan, "
            "mengambil transcript video, dan membuat tutorial lengkap dengan bahan, alat, "
            "dan langkah-langkah memasak berdasarkan timestamp nyata dari video."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "food_name": {
                    "type": "string",
                    "description": "Nama makanan atau minuman yang ingin dibuatkan tutorialnya",
                },
            },
            "required": ["food_name"],
        },
    },
    {
        "name": "get_recipe_by_id",
        "description": (
            "Gunakan tool ini ketika user ingin melihat kembali resep yang sudah pernah dibuat. "
            "Masukkan recipe_id dari ringkasan percakapan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "recipe_id": {
                    "type": "string",
                    "description": "UUID recipe yang ingin diperiksa",
                },
            },
            "required": ["recipe_id"],
        },
    },
]

SYSTEM_PROMPT = """Kamu adalah asisten pintar bernama "ImHungry" yang membantu user menemukan resep dan tutorial memasak.

Kemampuanmu:
- Menjawab pertanyaan umum seputar makanan, memasak, dan kuliner
- Memanggil `ai_tutorial_generator` ketika user ingin membuat resep atau tutorial BARU
- Memanggil `get_recipe_by_id` ketika user ingin melihat resep yang sudah pernah dibuat sebelumnya

Aturan penting:
- JANGAN pernah menyebut recipe_id atau UUID kepada user dalam jawabanmu
- KAMU WAJIB selalu membalas dengan teks kepada user, tidak boleh diam atau mengembalikan respons kosong
- JANGAN mengarang atau menebak isi recipe — jika user meminta melihat recipe lama, KAMU WAJIB memanggil `get_recipe_by_id` menggunakan ID dari ringkasan percakapan
- Ketika recipe berhasil ditampilkan (dari tool manapun), KAMU WAJIB menulis 2-3 kalimat berisi:
  1. Kalimat pembuka yang menyebut nama makanan
  2. Ringkasan singkat: jumlah bahan dan estimasi budget dari hasil tool
  3. Kalimat penutup (contoh: "Selamat memasak!")
- JANGAN tulis ulang isi detail recipe — cukup ringkasan di atas, data lengkap otomatis ditampilkan sistem
- Jika user bertanya hal umum → jawab langsung tanpa tool
- Selalu ramah dan gunakan Bahasa Indonesia
"""


# ---------------------------------------------------------------------------
# Core: proses pesan user
# ---------------------------------------------------------------------------

def process_message(
    payload: ChatMessageRequest,
    current_user: dict,
    db: Session,
) -> ChatMessageResponse:
    """
    Proses satu pesan user dalam sebuah chat session.
    Dipanggil oleh FastAPI endpoint di routers/chat.py.
    """
    from fastapi import HTTPException

    if not payload.message:
        raise HTTPException(status_code=400, detail="Message is required")

    user_id = int(current_user["sub"])
    user_message = payload.message
    print(f"📩 [GeneralAI] user_id={user_id} msg={user_message[:60]}", flush=True)

    # Ambil lokasi user dari DB
    user = db.query(User).filter(User.id == user_id).first()
    user_location = (user.location or "") if user else ""

    # --- Session management ---
    if payload.session_id:
        chat_session = db.query(Chat).filter(
            Chat.id == payload.session_id,
            Chat.user_id == user_id,
        ).first()
        if not chat_session:
            raise HTTPException(status_code=404, detail="Session tidak ditemukan")
        stored_messages: list = list(chat_session.messages or [])
        is_new_session = False
    else:
        chat_session = Chat(
            id=uuid_module.uuid4(),
            user_id=user_id,
            title=None,
            messages=[],
            summary=None,
        )
        db.add(chat_session)
        db.flush()
        stored_messages = []
        is_new_session = True

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    tools = types.Tool(function_declarations=TOOL_DECLARATIONS)
    config = types.GenerateContentConfig(
        tools=[tools],
        system_instruction=SYSTEM_PROMPT,
    )

    try:
        # Update summary dari percakapan sebelumnya (best-effort)
        if stored_messages:
            try:
                update_summary(chat_session)
            except Exception as e:
                print(f"⚠️ [Summary] Failed: {e}", flush=True)

        # Bangun context dari summary (hemat token — bukan full history)
        history: list[types.Content] = []
        if chat_session.summary:
            history.append(types.Content(
                role="user",
                parts=[types.Part(text=f"[Ringkasan percakapan sebelumnya]\n{chat_session.summary}")],
            ))
            history.append(types.Content(
                role="model",
                parts=[types.Part(text="Baik, saya sudah memahami konteks percakapan sebelumnya.")],
            ))
        history.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            config=config,
            contents=history,
        )

        generated_recipe_id: str | None = None

        for iteration in range(5):
            if not response.candidates:
                break

            model_content = response.candidates[0].content
            history.append(model_content)

            function_calls = [
                part.function_call
                for part in model_content.parts
                if hasattr(part, "function_call") and part.function_call
            ]

            if not function_calls:
                break

            print(f"🔧 [GeneralAI] Iteration {iteration + 1}: {len(function_calls)} call(s)", flush=True)

            tool_responses, recipe_id_from_tools = handle_tool_calls(
                function_calls, user_location, db, chat_session.id, user_id
            )
            if recipe_id_from_tools:
                generated_recipe_id = recipe_id_from_tools

            history.append(types.Content(
                role="user",
                parts=[types.Part(function_response=fr) for fr in tool_responses],
            ))

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                config=config,
                contents=history,
            )

        # Ekstrak teks intro dari Gemini
        ai_intro_text = ""
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    ai_intro_text = part.text.strip()
                    break

        if not ai_intro_text:
            if generated_recipe_id:
                ai_intro_text = "Baik! Tutorial memasak sudah berhasil saya siapkan untuk Anda. Selamat memasak!"
            else:
                ai_intro_text = "Maaf, saya tidak bisa memproses permintaan ini."

        # Simpan entry baru ke chat.messages
        new_entry: dict = {"question": user_message, "answer": ai_intro_text}
        if generated_recipe_id:
            new_entry["recipe_id"] = generated_recipe_id

        updated_messages = stored_messages + [new_entry]

        if is_new_session:
            chat_session.title = user_message[:60] + ("..." if len(user_message) > 60 else "")

        chat_session.messages = updated_messages
        db.commit()
        db.refresh(chat_session)

        print(
            f"✅ [GeneralAI] Session {chat_session.id} | "
            f"total_msg={len(updated_messages)} | recipe_id={generated_recipe_id}",
            flush=True,
        )

        # Kembalikan hanya pesan BARU (history lengkap via endpoint terpisah)
        new_message_response = enrich_with_recipe([new_entry], db)

        return ChatMessageResponse(
            session_id=chat_session.id,
            messages=new_message_response,
        )

    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
