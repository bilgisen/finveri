from typing import Optional
from pydantic import BaseModel


class ItemCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    is_available: bool = True


class Item(ItemCreate):
    id: int

    class Config:
        orm_mode = True
