import json
import os
import uuid as uuid_module

import googleapiclient.discovery
import googleapiclient.errors
from fastapi import APIRouter, Depends, HTTPException
from google import genai
from google.genai import types
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.security import get_current_user
from db.session import get_db
from dotenv import load_dotenv
from models.chat import Chat
from models.recipe_local import RecipeLocal
from models.user import User
from schemas.chat import ChatMessageRequest, ChatMessageResponse, ChatHistoryItem, MessageEntry

load_dotenv()

router = APIRouter(prefix="/chat", tags=["chat"])

GEMINI_MODEL = "gemini-2.0-flash"


# ---------------------------------------------------------------------------
# Pydantic schema untuk structured output ai_tutorial_generator
# ---------------------------------------------------------------------------

class _ToolItem(BaseModel):
    name: str
    value: int | None = None


class _Ingredient(BaseModel):
    name: str
    amount: str
    price: int


class _CookingTool(BaseModel):
    name: str
    amount: str


class _Step(BaseModel):
    timestamp: int
    instruction: str
    tools: list[_ToolItem]


class _Tutorial(BaseModel):
    ingredients: list[_Ingredient]
    tools: list[_CookingTool]
    steps: list[_Step]


class _TutorialOutput(BaseModel):
    estimated_budget: int
    video_id: str
    tutorial: _Tutorial


# ---------------------------------------------------------------------------
# Helper: YouTube search
# ---------------------------------------------------------------------------

def _youtube_search(query: str, max_results: int = 5) -> list:
    api_key = os.getenv("YOUTUBE_API")
    if not api_key:
        raise RuntimeError("YOUTUBE_API key tidak ditemukan di environment")

    youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
    response = youtube.search().list(
        part="snippet",
        q=query,
        maxResults=max_results,
        type="video",
    ).execute()

    return [
        {
            "video_id": item["id"]["videoId"],
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
            "description": item["snippet"]["description"],
        }
        for item in response.get("items", [])
    ]


# ---------------------------------------------------------------------------
# Tool 1: ai_tutorial_generator
# Menghasilkan recipe, menyimpan ke recipe_local.
# Mengembalikan data minimal ke Gemini (hanya recipe_id + title).
# Data recipe lengkap disimpan di DB dan disisipkan backend ke response user.
# ---------------------------------------------------------------------------

def ai_tutorial_generator(
    food_name: str,
    user_location: str = "",
    db: Session = None,
    session_id=None,
    user_id: int = None,
) -> dict:
    print(f"🍳 [TutorialAI] food={food_name} location={user_location}", flush=True)

    try:
        videos = _youtube_search(f"{food_name} resep tutorial cara membuat")
    except Exception as e:
        return {"error": f"Gagal mencari YouTube: {str(e)}"}

    if not videos:
        return {"error": "Tidak ada video YouTube yang ditemukan"}

    best_video = videos[0]
    video_id = best_video["video_id"]
    video_title = best_video["title"]
    video_description = best_video["description"]
    print(f"🎬 [TutorialAI] Video: {video_title} ({video_id})", flush=True)

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    location_ctx = f"Lokasi user: {user_location}. " if user_location else ""

    prompt = f"""Kamu adalah asisten memasak yang ahli.
{location_ctx}Berdasarkan video YouTube berikut tentang "{food_name}":
- Judul: {video_title}
- Deskripsi: {video_description}

Buat tutorial memasak lengkap dalam Bahasa Indonesia:
- Daftar bahan-bahan beserta harga satuan Rupiah (IDR), sesuaikan dengan lokasi user
- Alat masak yang dibutuhkan
- Langkah-langkah memasak dengan timestamp (detik) dan alat di setiap langkah
- Estimasi total budget Rupiah (2026)

video_id harus diisi dengan: {video_id}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_TutorialOutput,
        ),
    )

    tutorial_data = json.loads(response.text)
    tutorial_data["video_id"] = video_id

    recipe_id = uuid_module.uuid4()
    recipe_row = RecipeLocal(
        id=recipe_id,
        title=food_name,
        session_id=session_id,
        user_id=user_id,
        recipe=tutorial_data,
    )
    db.add(recipe_row)
    db.flush()

    print(f"💾 [TutorialAI] Saved recipe_id={recipe_id}", flush=True)

    # Kembalikan data MINIMAL ke Gemini — recipe lengkap tidak dikirim balik ke LLM
    # agar backend yang menyisipkannya ke response user
    return {
        "status": "berhasil",
        "recipe_id": str(recipe_id),
        "food_name": food_name,
        "video_title": video_title,
        "jumlah_bahan": len(tutorial_data.get("tutorial", {}).get("ingredients", [])),
        "jumlah_langkah": len(tutorial_data.get("tutorial", {}).get("steps", [])),
        "estimated_budget": tutorial_data.get("estimated_budget", 0),
        # Simpan recipe lengkap di field terpisah untuk diambil backend (tidak terlihat Gemini)
        "_recipe_data": tutorial_data,
    }


# ---------------------------------------------------------------------------
# Tool 2: get_recipe_by_id
# AI memanggil ini saat ingin memeriksa detail recipe yang sudah tersimpan.
# ---------------------------------------------------------------------------

def get_recipe_by_id(recipe_id: str, db: Session) -> dict:
    recipe_row = db.query(RecipeLocal).filter(
        RecipeLocal.id == recipe_id
    ).first()

    if not recipe_row:
        return {"error": f"Recipe dengan ID {recipe_id} tidak ditemukan"}

    recipe_data = recipe_row.recipe
    # Kembalikan data MINIMAL ke Gemini — recipe lengkap disimpan di _recipe_data
    # untuk disisipkan backend ke response user (tidak dikirim ke Gemini)
    return {
        "status": "ditemukan",
        "recipe_id": str(recipe_row.id),
        "title": recipe_row.title,
        "jumlah_bahan": len(recipe_data.get("tutorial", {}).get("ingredients", [])),
        "jumlah_langkah": len(recipe_data.get("tutorial", {}).get("steps", [])),
        "estimated_budget": recipe_data.get("estimated_budget", 0),
        "_recipe_data": recipe_data,
    }


# ---------------------------------------------------------------------------
# Tool declarations untuk Gemini
# ---------------------------------------------------------------------------

_TOOL_DECLARATIONS = [
    {
        "name": "ai_tutorial_generator",
        "description": (
            "Gunakan tool ini ketika user meminta resep, tutorial memasak, atau cara membuat "
            "makanan/minuman tertentu. Tool ini akan mencari video YouTube yang relevan dan "
            "membuat tutorial lengkap dengan bahan, alat, dan langkah-langkah memasak."
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
            "Gunakan tool ini ketika kamu perlu memeriksa detail recipe yang sudah tersimpan. "
            "Masukkan recipe_id dari riwayat percakapan untuk mendapatkan data lengkap."
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

_GENERAL_AI_SYSTEM_PROMPT = """Kamu adalah asisten pintar bernama "ImHungry" yang membantu user menemukan resep dan tutorial memasak.

Kemampuanmu:
- Menjawab pertanyaan umum seputar makanan, memasak, dan kuliner
- Memanggil `ai_tutorial_generator` ketika user ingin membuat resep atau tutorial BARU
- Memanggil `get_recipe_by_id` ketika user ingin melihat resep yang sudah pernah dibuat sebelumnya

Aturan penting:
- JANGAN pernah menyebut recipe_id atau UUID kepada user dalam jawabanmu
- KAMU WAJIB selalu membalas dengan teks kepada user, tidak boleh diam atau mengembalikan respons kosong
- JANGAN mengarang atau menebak isi recipe — jika user meminta melihat recipe lama, KAMU WAJIB memanggil `get_recipe_by_id` menggunakan ID dari ringkasan percakapan
- Ketika recipe berhasil ditampilkan (dari `ai_tutorial_generator` atau `get_recipe_by_id`), KAMU WAJIB menulis 2-3 kalimat berisi:
  1. Kalimat pembuka yang menyebut nama makanan
  2. Ringkasan singkat: jumlah bahan dan estimasi budget dari hasil tool
  3. Kalimat penutup (contoh: "Selamat memasak!")
- JANGAN tulis ulang isi detail recipe — cukup ringkasan di atas, data lengkap otomatis ditampilkan sistem
- Jika user bertanya hal umum → jawab langsung tanpa tool
- Selalu ramah dan gunakan Bahasa Indonesia
"""


# ---------------------------------------------------------------------------
# Fungsi summary: merangkum isi chat.messages menjadi teks ringkas
# Dipanggil setiap ada pesan masuk untuk update konteks LLM
# Tidak menyertakan JSON recipe — hanya UUID reference
# ---------------------------------------------------------------------------

def _update_summary(chat_session: Chat, db: Session) -> None:
    """
    Buat/update ringkasan percakapan dari chat.messages.
    Ringkasan disimpan di chat.summary dan digunakan sebagai konteks LLM
    untuk menghemat token (menggantikan full history).
    """
    messages = chat_session.messages or []
    if not messages:
        return

    # Susun log percakapan untuk disimpulkan — tanpa JSON recipe
    log_parts = []
    for msg in messages:
        question = msg.get("question", "")
        answer = msg.get("answer", "")
        recipe_id = msg.get("recipe_id")

        # Potong answer panjang (recipe data sudah dipisah ke recipe_local)
        if len(answer) > 300:
            answer = answer[:300] + "..."

        entry = f"User: {question}\nAI: {answer}"
        if recipe_id:
            entry += f"\n[Recipe dibuat, ID: {recipe_id}]"
        log_parts.append(entry)

    log_text = "\n\n".join(log_parts)

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=(
            "Buat ringkasan percakapan berikut dalam 3-5 kalimat Bahasa Indonesia yang ringkas. "
            "Fokus pada: apa yang user inginkan, apa yang sudah dibahas, dan makanan apa yang sudah dibuatkan resepnya. "
            "Jika ada recipe yang dibuat, sebutkan nama makanannya dan UUID-nya saja, jangan tulis isi recipe. "
            "Jangan tambahkan komentar atau penjelasan ekstra.\n\n"
            f"Percakapan:\n{log_text}"
        ),
    )

    chat_session.summary = response.text.strip()
    print(f"📝 [Summary] Updated for session {chat_session.id}", flush=True)


# ---------------------------------------------------------------------------
# Helper: handle tool calls dari Gemini
# ---------------------------------------------------------------------------

def _handle_tool_calls(
    function_calls: list,
    user_location: str,
    db: Session,
    session_id,
    user_id: int = None,
) -> tuple[list[types.FunctionResponse], str | None, dict | None]:
    """
    Jalankan setiap tool call.
    Return: (gemini_responses, recipe_id_jika_ada, recipe_data_lengkap_jika_ada)
    """
    responses = []
    generated_recipe_id: str | None = None
    generated_recipe_data: dict | None = None

    for fc in function_calls:
        tool_name = fc.name
        arguments = dict(fc.args)
        print(f"🔨 [GeneralAI] Tool={tool_name} args={arguments}", flush=True)

        if tool_name == "ai_tutorial_generator":
            result = ai_tutorial_generator(
                user_location=user_location,
                db=db,
                session_id=session_id,
                user_id=user_id,
                **arguments,
            )
            if "recipe_id" in result:
                generated_recipe_id = result["recipe_id"]
                generated_recipe_data = result.pop("_recipe_data", None)

        elif tool_name == "get_recipe_by_id":
            result = get_recipe_by_id(db=db, **arguments)
            if result.get("status") == "ditemukan" and "recipe_id" in result:
                # Capture recipe_id agar backend bisa sertakan recipe di response
                generated_recipe_id = result["recipe_id"]
                generated_recipe_data = result.pop("_recipe_data", None)

        else:
            result = {"error": f"Tool '{tool_name}' tidak ditemukan"}

        print(f"📊 [GeneralAI] Tool result keys={list(result.keys()) if isinstance(result, dict) else result}", flush=True)
        responses.append(types.FunctionResponse(name=tool_name, response={"result": result}))

    return responses, generated_recipe_id, generated_recipe_data


# ---------------------------------------------------------------------------
# Helper: fetch recipe untuk disertakan di response API
# ---------------------------------------------------------------------------

def _enrich_messages_with_recipe(stored_messages: list, db: Session) -> list[MessageEntry]:
    """
    Untuk setiap pesan yang memiliki recipe_id, fetch data recipe dari recipe_local
    dan sisipkan ke field `recipe` pada MessageEntry (hanya untuk response API).
    """
    result = []
    for msg in stored_messages:
        entry = MessageEntry(
            question=msg.get("question", ""),
            answer=msg.get("answer", ""),
            recipe_id=msg.get("recipe_id"),
        )
        if entry.recipe_id:
            recipe_row = db.query(RecipeLocal).filter(
                RecipeLocal.id == entry.recipe_id
            ).first()
            if recipe_row:
                entry.recipe = recipe_row.recipe
        result.append(entry)
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/message", response_model=ChatMessageResponse)
def send_message(
    payload: ChatMessageRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
    tools = types.Tool(function_declarations=_TOOL_DECLARATIONS)
    config = types.GenerateContentConfig(
        tools=[tools],
        system_instruction=_GENERAL_AI_SYSTEM_PROMPT,
    )

    try:
        # --- Update summary dari percakapan sebelumnya (best-effort, tidak kritis) ---
        if stored_messages:
            try:
                _update_summary(chat_session, db)
            except Exception as summary_err:
                print(f"⚠️ [Summary] Failed to update: {summary_err}", flush=True)

        # --- Bangun context LLM dari summary (bukan full history) ---
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
        generated_recipe_data: dict | None = None

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

            tool_responses, recipe_id_from_tools, recipe_data_from_tools = _handle_tool_calls(
                function_calls, user_location, db, chat_session.id, user_id
            )
            if recipe_id_from_tools:
                generated_recipe_id = recipe_id_from_tools
            if recipe_data_from_tools:
                generated_recipe_data = recipe_data_from_tools  # noqa: F841

            history.append(types.Content(
                role="user",
                parts=[types.Part(function_response=fr) for fr in tool_responses],
            ))

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                config=config,
                contents=history,
            )

        # Ekstrak teks pengantar dari Gemini (kata-kata AI, tanpa recipe)
        ai_intro_text = ""
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "text") and part.text:
                    ai_intro_text = part.text.strip()
                    break

        if not ai_intro_text:
            if generated_recipe_id:
                # Gemini diam padahal recipe berhasil dibuat — buat fallback informatif
                ai_intro_text = "Baik! Tutorial memasak sudah berhasil saya siapkan untuk Anda. Selamat memasak!"
            else:
                ai_intro_text = "Maaf, saya tidak bisa memproses permintaan ini."

        # --- Susun entry pesan yang disimpan ke chat.messages ---
        # answer = hanya teks AI (bukan recipe JSON)
        # recipe_id = UUID recipe jika dihasilkan
        new_entry: dict = {
            "question": user_message,
            "answer": ai_intro_text,
        }
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

        # --- Susun response ke client ---
        # Hanya kembalikan pesan BARU saja (bukan seluruh history session)
        # History lengkap bisa diambil via GET /chat/history/{user_id}
        new_message_response = _enrich_messages_with_recipe([new_entry], db)

        return ChatMessageResponse(
            session_id=chat_session.id,
            messages=new_message_response,
        )

    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/history/{user_id}", response_model=list[ChatHistoryItem])
def get_chat_history(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    requester_id = int(current_user["sub"])
    if requester_id != user_id:
        raise HTTPException(status_code=403, detail="Tidak bisa mengakses history user lain")

    sessions = (
        db.query(Chat)
        .filter(Chat.user_id == user_id)
        .order_by(Chat.created_at.desc())
        .all()
    )

    return [
        ChatHistoryItem(
            session_id=s.id,
            title=s.title,
            created_at=s.created_at,
        )
        for s in sessions
    ]
