from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SendMessageResult:
    success: bool
    provider_message_id: Optional[str] = None
    status: Optional[str] = None          # e.g. "queued", "sent", "failed"
    error_message: Optional[str] = None
    raw_response: Optional[dict] = None    # keep the raw payload for debugging/logs


@dataclass
class IncomingMessage:
    from_number: str          # customer's number, E.164 format, no "whatsapp:" prefix
    to_number: str             # your business number that received it
    body: str
    provider_message_id: Optional[str] = None
    media_urls: Optional[list] = None
    raw_payload: Optional[dict] = None


class WhatsAppProvider(ABC):

    @abstractmethod
    def send_text_message(self, to: str, body: str) -> SendMessageResult:
        raise NotImplementedError

    @abstractmethod
    def send_template_message(
        self,
        to: str,
        template_id: str,
        variables: Optional[dict] = None,
    ) -> SendMessageResult:
        raise NotImplementedError

    @abstractmethod
    def parse_incoming_webhook(self, request) -> IncomingMessage:
        raise NotImplementedError

    @abstractmethod
    def validate_webhook_signature(self, request) -> bool:
        raise NotImplementedError