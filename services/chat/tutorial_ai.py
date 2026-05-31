"""
AI spesialis untuk generate tutorial memasak.
Alur:
  1. Cari video YouTube yang relevan
  2. Ambil transcript video (fallback ke deskripsi jika tidak ada transcript)
  3. Generate structured tutorial (bahan, alat, langkah, budget) dengan Gemini
  4. Simpan ke tabel recipe_local
  5. Kembalikan data minimal ke General AI (recipe lengkap disisipkan backend)
"""
import json
import os
import uuid as uuid_module

from google import genai
from google.genai import types
from sqlalchemy.orm import Session

from models.recipe_local import RecipeLocal
from services.chat.schemas import TutorialOutput
from services.chat.youtube import youtube_search, fetch_transcript

GEMINI_MODEL = "gemini-2.0-flash"


def ai_tutorial_generator(
    food_name: str,
    user_location: str = "",
    db: Session = None,
    session_id=None,
    user_id: int = None,
) -> dict:
    """
    Generate tutorial memasak untuk makanan tertentu.

    Returns dict dengan data minimal untuk Gemini + '_recipe_data' untuk backend.
    '_recipe_data' TIDAK dikirim ke Gemini — hanya untuk backend menyisipkan ke response user.
    """
    print(f"🍳 [TutorialAI] food={food_name} location={user_location}", flush=True)

    # Step 1: Cari video YouTube
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

    # Step 2: Ambil transcript video
    transcript_text = fetch_transcript(video_id)

    # Step 3: Build prompt
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
Buat tutorial memasak lengkap dalam Bahasa Indonesia:
- Daftar bahan-bahan beserta harga satuan Rupiah (IDR), sesuaikan harga dengan lokasi user
- Alat masak yang dibutuhkan
- Langkah-langkah memasak dengan timestamp (detik dari transcript) dan alat yang digunakan
- Estimasi total budget Rupiah (2026)

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

    # Step 4: Simpan ke recipe_local
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

    # Step 5: Kembalikan data MINIMAL ke Gemini
    return {
        "status": "berhasil",
        "recipe_id": str(recipe_id),
        "food_name": food_name,
        "video_title": video_title,
        "jumlah_bahan": len(tutorial_data.get("tutorial", {}).get("ingredients", [])),
        "jumlah_langkah": len(tutorial_data.get("tutorial", {}).get("steps", [])),
        "estimated_budget": tutorial_data.get("estimated_budget", 0),
        "_recipe_data": tutorial_data,
    }
