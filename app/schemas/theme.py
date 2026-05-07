from pydantic import BaseModel


class Theme(BaseModel):
    theme_id: int
    name: str
    description: str
    preview_color: str
