# START OF FILE: src/domain/models.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    id: int
    username: Optional[str]
    first_name: Optional[str]
    utm_source: Optional[str] = None

@dataclass
class Lead:
    user_id: int
    name: str
    debt_amount: str
    income_source: str
    region: str

@dataclass
class Message:
    role: str  # 'user' or 'assistant'
    content: str

# END OF FILE: src/domain/models.py