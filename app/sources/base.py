"""
Her veri kaynağının implement etmesi gereken abstract base class.
Yeni bir kaynak eklemek için bu sınıfı miras alıp fetch() metodunu doldurmak yeterli.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SourceResult:
    """fetch() metodunun döndürdüğü standart sonuç."""
    success: bool
    data: List[dict] = field(default_factory=list)
    error: Optional[str] = None
    fetched_at: Optional[datetime] = None


class BaseSource(ABC):
    """
    Tüm veri kaynaklarının temel sınıfı.

    Her kaynak:
    - Kendi URL'inden ham veri çeker
    - Ham veriyi ortak Instrument formatına normalize eder
    - SourceResult döner
    """

    # Kaynağın benzersiz adı (Redis key'lerinde ve loglarda kullanılır)
    name: str = "base"

    # Bu kaynak hangi veri tiplerini sağlıyor?
    # Örn: ["instruments", "bist_stocks", "forex"]
    provides: List[str] = []

    @abstractmethod
    def fetch(self) -> SourceResult:
        """
        Kaynaktan veri çeker ve normalize edilmiş SourceResult döner.
        Hata durumunda exception fırlatmak yerine success=False döndürülmeli.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Source: {self.name}>"
