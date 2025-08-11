# START OF FILE: src/domain/models.py

from dataclasses import dataclass, asdict
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
    
    # ИСПРАВЛЕНИЕ: Добавляем метод для сериализации в словарь, чтобы починить /last_answer
    def to_dict(self):
        return asdict(self)

# END OF FILE: src/domain/models.py