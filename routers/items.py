from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/items", tags=["items"])

_items: list[dict] = [
    {"id": 1, "name": "Nasi Goreng", "description": "Nasi goreng spesial"},
    {"id": 2, "name": "Mie Ayam", "description": "Mie ayam pangsit"},
]
_next_id = 3


class ItemCreate(BaseModel):
    name: str
    description: str | None = None


class Item(ItemCreate):
    id: int


@router.get("", response_model=list[Item])
def list_items():
    return _items


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int):
    for item in _items:
        if item["id"] == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item not found")


@router.post("", response_model=Item, status_code=201)
def create_item(payload: ItemCreate):
    global _next_id
    item = {"id": _next_id, **payload.model_dump()}
    _items.append(item)
    _next_id += 1
    return item
