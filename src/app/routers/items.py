from typing import Dict, List
from fastapi import APIRouter, HTTPException
from app.models.item import Item, ItemCreate

router = APIRouter(
    prefix="/items",
    tags=["items"],
)

# Geçici in-memory veri deposu
fake_db: Dict[int, Item] = {}
counter = 0


@router.get("/", response_model=List[Item])
def get_items():
    """Tüm item'ları listele"""
    return list(fake_db.values())


@router.get("/{item_id}", response_model=Item)
def get_item(item_id: int):
    """Belirli bir item'ı getir"""
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item bulunamadı")
    return fake_db[item_id]


@router.post("/", response_model=Item, status_code=201)
def create_item(item: ItemCreate):
    """Yeni bir item oluştur"""
    global counter
    counter += 1
    new_item = Item(id=counter, **item.dict())
    fake_db[counter] = new_item
    return new_item


@router.put("/{item_id}", response_model=Item)
def update_item(item_id: int, item: ItemCreate):
    """Mevcut bir item'ı güncelle"""
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item bulunamadı")
    updated_item = Item(id=item_id, **item.dict())
    fake_db[item_id] = updated_item
    return updated_item


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int):
    """Bir item'ı sil"""
    if item_id not in fake_db:
        raise HTTPException(status_code=404, detail="Item bulunamadı")
    del fake_db[item_id]
