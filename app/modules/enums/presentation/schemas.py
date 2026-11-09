from pydantic import BaseModel


class EnumOptionResponse(BaseModel):
    value: str
    label: str
