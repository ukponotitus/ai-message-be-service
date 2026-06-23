from django.db import models
from automation.models import Business


class Transaction(models.Model):
    STATUS_CHOICES = [('pending', 'Pending'), ('success', 'Success'), ('failed', 'Failed')]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="transactions")
    reference = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_length=10, decimal_places=2, max_digits=12)
    plan_type = models.CharField(max_length=50)
    billing_cycle = models.CharField(max_length=10, default='monthly')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.business.name} - {self.reference} ({self.status})"


class Subscription(models.Model):
    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name="subscription")
    plan = models.CharField(max_length=20, default='free')
    billing_cycle = models.CharField(max_length=10, default='monthly')
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    complimentary = models.BooleanField(default=False, help_text="Super admin grants free permanent access")

    def __str__(self):
        return f"{self.business.name} - {self.plan} ({self.billing_cycle})"
