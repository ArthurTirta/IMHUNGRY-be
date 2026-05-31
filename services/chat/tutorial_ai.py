"""
AI spesialis untuk generate tutorial memasak.

Satu tool dengan dua mode:
  1. CREATE  — food_name saja → cari YouTube, generate resep baru, simpan ke library
  2. QUERY   — recipe_id + query → jawab pertanyaan / perbarui resep yang sudah ada

Output bisa berupa teks saja, resep (JSON), atau keduanya.
"""
import json
import os
import uuid as uuid_module

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from models.library import Library
from services.chat.schemas import TutorialOutput, TutorialQueryOutput
from services.chat.youtube import youtube_search, fetch_transcript

GEMINI_MODEL = "gemini-2.0-flash"


def _minimal_result(
    recipe_id: str,
    food_name: str,
    recipe_data: dict,
    *,
    text: str | None = None,
    response_type: str = "recipe",
) -> dict:
    """Bangun dict return standar; _recipe_data hanya untuk backend."""
    tutorial = recipe_data.get("tutorial", {})
    result = {
        "status": "berhasil",
        "response_type": response_type,
        "recipe_id": recipe_id,
        "food_name": food_name,
        "jumlah_bahan": len(tutorial.get("ingredients", [])),
        "jumlah_langkah": len(tutorial.get("steps", [])),
        "estimated_budget": recipe_data.get("estimated_budget", 0),
        "_recipe_data": recipe_data,
    }
    if text:
        result["text"] = text
    return result


def _create_new_recipe(
    food_name: str,
    user_location: str,
    db: Session,
    session_id,
    user_id,
) -> dict:
    print(f"🍳 [TutorialAI] CREATE food={food_name} location={user_location}", flush=True)

    try:
        videos = youtube_search(f"{food_name} resep tutorial cara membuat")
    except Exception as e:
        return {"error": f"Gagal mencari YouTube: {str(e)}"}

    if not videos:
        return {"error": "Tidak ada video YouTube yang ditemukan"}

    best_video = videos[0]
    video_id = best_video["video_id"]
    video_title = best_video["title"]
    video_description = best_video["description"]
    print(f"🎬 [TutorialAI] Video: {video_title} ({video_id})", flush=True)

    transcript_text = fetch_transcript(video_id)
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    location_ctx = f"Lokasi user: {user_location}. " if user_location else ""

    if transcript_text:
        source_section = f"""
Transcript video (dengan timestamp dalam detik):
{transcript_text}

Gunakan timestamp dari transcript di atas untuk menentukan waktu setiap langkah memasak.
"""
    else:
        source_section = f"""
Deskripsi video: {video_description}
(Transcript tidak tersedia — estimasikan timestamp berdasarkan urutan langkah memasak.)
"""

    prompt = f"""Kamu adalah asisten memasak yang ahli.
{location_ctx}Berdasarkan video YouTube berikut tentang "{food_name}":
- Judul: {video_title}{source_section}
Buat tutorial memasak lengkap dalam Bahasa Indonesia dengan ketentuan berikut:

1. Daftar bahan-bahan beserta harga satuan Rupiah (IDR), sesuaikan harga dengan lokasi user.
2. Daftar alat masak yang dibutuhkan (tools utama, bukan per-langkah).
3. Langkah-langkah memasak dengan:
   - timestamp: detik dari transcript (atau estimasi bila tidak ada transcript)
   - instruction: instruksi singkat dan jelas
   - tools: daftar alat yang dipakai di langkah ini. Untuk SETIAP alat:
     * name: nama alat
     * timer_seconds: isi HANYA bila langkah ini membutuhkan waktu tunggu spesifik
       (contoh: goreng 10 menit → 600). Bila tidak ada waktu tunggu, isi null.
       PENTING: timer_seconds adalah durasi tunggu (bukan timestamp video).
4. Estimasi total budget Rupiah (2026).

video_id harus diisi dengan: {video_id}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=TutorialOutput,
        ),
    )

    tutorial_data = json.loads(response.text)
    tutorial_data["video_id"] = video_id

    recipe_id = uuid_module.uuid4()
    recipe_row = Library(
        id=recipe_id,
        title=food_name,
        session_id=session_id,
        user_id=user_id,
        video_id=video_id,
        recipe=tutorial_data,
        visibility=0,
        stars=0,
    )
    db.add(recipe_row)
    db.flush()
    print(f"💾 [TutorialAI] CREATE saved recipe_id={recipe_id}", flush=True)

    return _minimal_result(str(recipe_id), food_name, tutorial_data, response_type="recipe")


def _handle_query(
    food_name: str,
    query: str,
    recipe_id: str,
    user_location: str,
    db: Session,
    user_id,
) -> dict:
    print(f"🔍 [TutorialAI] QUERY recipe_id={recipe_id} query={query[:80]}", flush=True)

    recipe_row = db.query(Library).filter(
        Library.id == recipe_id,
        Library.user_id == user_id,
    ).first()
    if not recipe_row:
        return {"error": f"Recipe dengan ID {recipe_id} tidak ditemukan"}

    existing_data = dict(recipe_row.recipe or {})
    title = food_name or recipe_row.title
    location_ctx = f"Lokasi user: {user_location}. " if user_location else ""

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    prompt = f"""Kamu adalah asisten memasak ahli yang membantu user memahami dan memperbaiki resep.

{location_ctx}Resep yang sedang dibahas: "{title}"

Data resep saat ini (JSON):
{json.dumps(existing_data, ensure_ascii=False, indent=2)}

Pertanyaan / permintaan user:
{query}

Tentukan response_type:
- "text"     → hanya jawab dengan teks (substitusi bahan, tips, klarifikasi). Jangan ubah resep.
- "recipe"   → user minta ubah resep (versi pedas, tambah bahan, kurangi porsi, dll). Isi tutorial lengkap yang diperbarui.
- "both"     → jawab pertanyaan SEKALIGUS perbarui resep.

Aturan:
- Field `text` WAJIB diisi — jawaban conversational Bahasa Indonesia untuk user (2-5 kalimat).
- Jika response_type "text", biarkan estimated_budget, video_id, tutorial = null.
- Jika response_type "recipe" atau "both", isi tutorial lengkap (ingredients, tools, steps dengan timer_seconds).
- Pertahankan video_id yang sama: {existing_data.get("video_id", recipe_row.video_id)}
- Jangan mengarang bahan/langkah yang tidak relevan dengan pertanyaan user.
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=TutorialQueryOutput,
        ),
    )

    parsed = json.loads(response.text)
    response_type = parsed.get("response_type", "text")
    answer_text = parsed.get("text", "").strip()

    if not answer_text:
        answer_text = "Maaf, saya tidak bisa menjawab pertanyaan ini saat ini."

    # Mode teks saja — resep tidak diubah
    if response_type == "text":
        print(f"💬 [TutorialAI] QUERY text-only recipe_id={recipe_id}", flush=True)
        return _minimal_result(
            str(recipe_row.id),
            title,
            existing_data,
            text=answer_text,
            response_type="text",
        )

    # Mode update resep
    updated_data = {
        "estimated_budget": parsed.get("estimated_budget") or existing_data.get("estimated_budget", 0),
        "video_id": parsed.get("video_id") or existing_data.get("video_id", recipe_row.video_id),
        "tutorial": parsed.get("tutorial") or existing_data.get("tutorial", {}),
    }
    recipe_row.recipe = updated_data
    if food_name:
        recipe_row.title = food_name
    db.flush()
    print(f"📝 [TutorialAI] QUERY updated recipe_id={recipe_id} type={response_type}", flush=True)

    return _minimal_result(
        str(recipe_row.id),
        recipe_row.title,
        updated_data,
        text=answer_text,
        response_type=response_type,
    )


def ai_tutorial_generator(
    food_name: str = "",
    query: str | None = None,
    recipe_id: str | None = None,
    user_location: str = "",
    db: Session = None,
    session_id=None,
    user_id: uuid_module.UUID = None,
) -> dict:
    """
    Tool tunggal untuk create resep baru atau follow-up query pada resep existing.

    CREATE : food_name (wajib)
    QUERY  : recipe_id + query (wajib keduanya)
    """
    if query and recipe_id:
        return _handle_query(
            food_name=food_name,
            query=query,
            recipe_id=recipe_id,
            user_location=user_location,
            db=db,
            user_id=user_id,
        )

    if not food_name:
        return {"error": "food_name wajib diisi untuk membuat resep baru"}

    return _create_new_recipe(
        food_name=food_name,
        user_location=user_location,
        db=db,
        session_id=session_id,
        user_id=user_id,
    )
