from django.conf import settings
from twilio.rest import Client
from twilio.request_validator import RequestValidator

from .base import WhatsAppProvider, SendMessageResult, IncomingMessage


class TwilioWhatsAppProvider(WhatsAppProvider):

    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_WHATSAPP_FROM
        self.client = Client(self.account_sid, self.auth_token)

    @staticmethod
    def _to_whatsapp_format(number: str) -> str:
        number = number.strip()
        if not number.startswith("whatsapp:"):
            number = f"whatsapp:{number}"
        return number

    def send_text_message(self, to: str, body: str) -> SendMessageResult:
        try:
            message = self.client.messages.create(
                from_=self.from_number,
                to=self._to_whatsapp_format(to),
                body=body,
            )
            return SendMessageResult(
                success=True,
                provider_message_id=message.sid,
                status=message.status,
                raw_response=message._properties,
            )
        except Exception as e:
            return SendMessageResult(
                success=False,
                error_message=str(e),
            )

    def send_template_message(
        self,
        to: str,
        template_id: str,
        variables: dict | None = None,
    ) -> SendMessageResult:
        try:
            message = self.client.messages.create(
                from_=self.from_number,
                to=self._to_whatsapp_format(to),
                content_sid=template_id,
                content_variables=str(variables) if variables else None,
            )
            return SendMessageResult(
                success=True,
                provider_message_id=message.sid,
                status=message.status,
                raw_response=message._properties,
            )
        except Exception as e:
            return SendMessageResult(
                success=False,
                error_message=str(e),
            )

    def parse_incoming_webhook(self, request) -> IncomingMessage:
        data = request.POST

        media_urls = []
        num_media = int(data.get("NumMedia", 0))
        for i in range(num_media):
            url = data.get(f"MediaUrl{i}")
            if url:
                media_urls.append(url)

        return IncomingMessage(
            from_number=data.get("From", "").replace("whatsapp:", ""),
            to_number=data.get("To", "").replace("whatsapp:", ""),
            body=data.get("Body", ""),
            provider_message_id=data.get("MessageSid"),
            media_urls=media_urls or None,
            raw_payload=dict(data),
        )

    def validate_webhook_signature(self, request) -> bool:
        validator = RequestValidator(self.auth_token)
        signature = request.META.get("HTTP_X_TWILIO_SIGNATURE", "")
        url = request.build_absolute_uri()
        params = request.POST.dict()
        return validator.validate(url, params, signature)