from database import Base
from encryption import EncryptedText
from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column


class PushSubscription(Base):
    """Store Web Push subscriptions per user.

    Endpoint and both subscription keys are encrypted at rest (#1329); reads
    transparently return plaintext. No query filters on these columns, so
    non-deterministic ciphertext is safe here.
    """

    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    p256dh: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    auth: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
