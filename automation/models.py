from django.db import models

# Create your models here.
class Contact(models.Model):
    # Change phone to blank/null=True so email-only users can be saved
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True) # Add this
    name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or self.email or self.phone


class Message(models.Model):
    ROLE_CHOICES = [("user", "User"), ("assistant", "Assistant")]
    STATUS_CHOICES = [("sent", "Sent"), ("failed", "Failed")]

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="sent")
    response_time = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

class CompanyInfo(models.Model):
    key = models.CharField(max_length=100, help_text="e.g., pricing, location, services")
    content = models.TextField(help_text="The actual details the AI should know")

    def __str__(self):
        return self.key

    class Meta:
        verbose_name_plural = "Company Info"