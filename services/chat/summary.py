"""
Fungsi untuk membuat dan memperbarui ringkasan percakapan (chat.summary).

Ringkasan digunakan sebagai konteks LLM pada request berikutnya,
menggantikan full history untuk menghemat penggunaan token.

Aturan:
- Tidak menyertakan JSON recipe (hanya UUID reference)
- Dipanggil sebagai best-effort — kegagalan tidak menghentikan request
"""
import os

from google import genai
from models.chat import Chat

GEMINI_MODEL = "gemini-2.0-flash"


def update_summary(chat_session: Chat) -> None:
    """
    Generate/update chat.summary dari isi chat.messages saat ini.
    Ringkasan disimpan ke chat_session.summary (in-memory, commit dilakukan di caller).
    """
    messages = chat_session.messages or []
    if not messages:
        return

    log_parts = []
    for msg in messages:
        question = msg.get("question", "")
        answer = msg.get("answer", "")
        recipe_id = msg.get("recipe_id")

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
