from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Contact, Message, CompanyInfo

admin.site.register(Contact)
admin.site.register(Message)
admin.site.register(CompanyInfo)