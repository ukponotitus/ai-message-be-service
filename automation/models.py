from django.db import models
from django.conf import settings


class Business(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    whatsapp_phone_number_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    whatsapp_access_token = models.CharField(max_length=500, blank=True, default="")
    system_prompt = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class BusinessMember(models.Model):
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("member", "Member"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_memberships",
    )
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="members"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "business")

    def __str__(self):
        return f"{self.user.email} -> {self.business.name} ({self.role})"


class ChannelConnection(models.Model):
    CHANNEL_TYPES = [
        ("whatsapp", "WhatsApp"),
        ("instagram", "Instagram"),
        ("facebook", "Facebook"),
        ("telegram", "Telegram"),
        ("email", "Email"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("disconnected", "Disconnected"),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="channels")
    channel_type = models.CharField(max_length=20, choices=CHANNEL_TYPES)
    name = models.CharField(max_length=100, blank=True)
    credentials = models.JSONField(default=dict, blank=True)
    phone_number_id = models.CharField(max_length=50, blank=True)
    access_token = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    webhook_verify_token = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("business", "channel_type", "phone_number_id")

    def __str__(self):
        return f"{self.business.name} - {self.get_channel_type_display()} ({self.name})"


class Contact(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="contacts", null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    name = models.CharField(max_length=100, blank=True)
    avatar_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    is_blocked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("business", "phone"), ("business", "email"))

    def __str__(self):
        return self.name or self.email or self.phone or f"Contact #{self.id}"


class Tag(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default="#6366f1")

    class Meta:
        unique_together = ("business", "name")

    def __str__(self):
        return self.name


class ContactTag(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="contact_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="contact_tags")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("contact", "tag")

    def __str__(self):
        return f"{self.contact} - {self.tag}"


class CustomField(models.Model):
    FIELD_TYPES = [
        ("text", "Text"),
        ("number", "Number"),
        ("date", "Date"),
        ("boolean", "Boolean"),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="custom_fields")
    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default="text")

    class Meta:
        unique_together = ("business", "name")

    def __str__(self):
        return f"{self.business.name} - {self.name}"


class ContactCustomField(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="custom_field_values")
    field = models.ForeignKey(CustomField, on_delete=models.CASCADE, related_name="values")
    value = models.TextField(blank=True)

    class Meta:
        unique_together = ("contact", "field")

    def __str__(self):
        return f"{self.contact} - {self.field.name}: {self.value}"


class Conversation(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("waiting", "Waiting"),
        ("resolved", "Resolved"),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="conversations")
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="conversations")
    channel = models.ForeignKey(ChannelConnection, on_delete=models.SET_NULL, null=True, blank=True, related_name="conversations")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_conversations")
    is_ai_enabled = models.BooleanField(default=True)
    last_message_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_message_at"]
        unique_together = ("business", "contact", "channel")

    def __str__(self):
        return f"{self.business.name} - {self.contact} ({self.status})"


class Message(models.Model):
    ROLE_CHOICES = [("user", "User"), ("assistant", "Assistant")]
    STATUS_CHOICES = [("sent", "Sent"), ("failed", "Failed")]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="messages", null=True, blank=True)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="messages")
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages", null=True, blank=True)
    channel = models.ForeignKey(ChannelConnection, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="sent")
    response_time = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business", "contact", "-created_at"]),
            models.Index(fields=["conversation", "-created_at"]),
        ]


class SocialAccount(models.Model):
    PROVIDER_CHOICES = [
        ("google", "Google"),
        ("facebook", "Facebook"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_accounts",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("provider", "provider_id")

    def __str__(self):
        return f"{self.user.email} ({self.provider})"


class CompanyInfo(models.Model):
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="company_info",
        null=True,
        blank=True,
    )
    key = models.TextField()
    content = models.TextField(blank=True, default="")

    def __str__(self):
        business_name = self.business.name if self.business else "No Business"
        return f"{business_name} - {self.key[:50]}"

    class Meta:
        verbose_name_plural = "Company Info"


class AutomationFlow(models.Model):
    TRIGGER_CHOICES = [
        ("message_received", "Message Received"),
        ("new_message", "New Message"),
        ("new_contact", "New Contact Created"),
        ("specific_keyword", "Specific Keyword"),
        ("keyword", "Keyword Match"),
        ("ad_click", "Ad Click"),
        ("webhook", "Webhook"),
        ("schedule", "Schedule"),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="automations")
    name = models.CharField(max_length=200)
    trigger = models.CharField(max_length=50, choices=TRIGGER_CHOICES, default="message_received")
    trigger_keywords = models.JSONField(default=list, blank=True)
    system_prompt = models.TextField(blank=True)
    is_active = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business.name} - {self.name}"


class Broadcast(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="broadcasts")
    name = models.CharField(max_length=200)
    channel = models.ForeignKey(ChannelConnection, on_delete=models.SET_NULL, null=True, blank=True, related_name="broadcasts")
    channel_type = models.CharField(max_length=20, blank=True, default="")
    email_subject = models.CharField(max_length=200, blank=True, default="")
    message_content = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    contacts = models.ManyToManyField(Contact, blank=True, related_name="broadcasts")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    total_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business.name} - {self.name}"


class BroadcastRecipient(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]
    broadcast = models.ForeignKey(Broadcast, on_delete=models.CASCADE, related_name="recipients")
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="broadcast_recipients")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("broadcast", "contact")
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.broadcast.name} -> {self.contact} ({self.status})"


class AnalyticsEvent(models.Model):
    EVENT_TYPES = [
        ("message_received", "Message Received"),
        ("message_sent", "Message Sent"),
        ("ai_reply", "AI Reply"),
        ("ai_failed", "AI Failed"),
        ("broadcast_sent", "Broadcast Sent"),
        ("broadcast_failed", "Broadcast Failed"),
        ("contact_created", "Contact Created"),
        ("human_handoff", "Human Handoff"),
        ("automation_triggered", "Automation Triggered"),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="analytics_events")
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    channel = models.ForeignKey(ChannelConnection, on_delete=models.SET_NULL, null=True, blank=True, related_name="analytics_events")
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name="analytics_events")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business", "event_type"]),
            models.Index(fields=["business", "created_at"]),
        ]

    def __str__(self):
        return f"{self.business.name} - {self.get_event_type_display()} ({self.created_at})"


class AutomationTrigger(models.Model):
    ACTION_CHOICES = [
        ("reply", "Reply with text"),
        ("tag", "Tag contact"),
        ("notify", "Notify owner"),
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="triggers")
    keyword = models.CharField(max_length=200)
    response_text = models.TextField(blank=True, default="")
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES, default="reply")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("business", "keyword")

    def __str__(self):
        return f"{self.business.name} - \"{self.keyword}\" ({self.get_action_type_display()})"
