"""
Fungsi-fungsi terkait operasi recipe di database:
- get_recipe_by_id     : fetch recipe dari recipe_local (dengan data minimal untuk Gemini)
- handle_tool_calls    : dispatcher tool call dari Gemini
- enrich_with_recipe   : inject data recipe ke MessageEntry untuk response API
"""
from google.genai import types
from sqlalchemy.orm import Session

from models.recipe_local import RecipeLocal
from schemas.chat import MessageEntry
from services.chat.tutorial_ai import ai_tutorial_generator


def get_recipe_by_id(recipe_id: str, db: Session) -> dict:
    """
    Fetch recipe dari tabel recipe_local.
    Kembalikan data MINIMAL ke Gemini — data lengkap ada di '_recipe_data' untuk backend.
    """
    recipe_row = db.query(RecipeLocal).filter(RecipeLocal.id == recipe_id).first()

    if not recipe_row:
        return {"error": f"Recipe dengan ID {recipe_id} tidak ditemukan"}

    recipe_data = recipe_row.recipe
    return {
        "status": "ditemukan",
        "recipe_id": str(recipe_row.id),
        "title": recipe_row.title,
        "jumlah_bahan": len(recipe_data.get("tutorial", {}).get("ingredients", [])),
        "jumlah_langkah": len(recipe_data.get("tutorial", {}).get("steps", [])),
        "estimated_budget": recipe_data.get("estimated_budget", 0),
        "_recipe_data": recipe_data,
    }


def handle_tool_calls(
    function_calls: list,
    user_location: str,
    db: Session,
    session_id,
    user_id: int = None,
) -> tuple[list[types.FunctionResponse], str | None]:
    """
    Jalankan setiap tool call dari Gemini.
    Return: (responses_for_gemini, recipe_id_jika_ada)

    '_recipe_data' di-pop dari result sebelum dikirim ke Gemini
    agar Gemini tidak melihat data besar dan tidak mengarang isi recipe.
    """
    responses = []
    captured_recipe_id: str | None = None

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
                captured_recipe_id = result["recipe_id"]
                result.pop("_recipe_data", None)

        elif tool_name == "get_recipe_by_id":
            result = get_recipe_by_id(db=db, **arguments)
            if result.get("status") == "ditemukan" and "recipe_id" in result:
                captured_recipe_id = result["recipe_id"]
                result.pop("_recipe_data", None)

        else:
            result = {"error": f"Tool '{tool_name}' tidak ditemukan"}

        print(f"📊 [GeneralAI] Tool result keys={list(result.keys())}", flush=True)
        responses.append(types.FunctionResponse(name=tool_name, response={"result": result}))

    return responses, captured_recipe_id


def enrich_with_recipe(stored_messages: list, db: Session) -> list[MessageEntry]:
    """
    Untuk setiap pesan yang memiliki recipe_id, fetch data recipe lengkap
    dari recipe_local dan sisipkan ke field `recipe` pada MessageEntry.
    Field ini HANYA untuk response API — tidak disimpan di chat.messages.
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
