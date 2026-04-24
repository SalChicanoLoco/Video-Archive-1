from pydantic import BaseModel


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict | list | str | None = None
    request_id: str
