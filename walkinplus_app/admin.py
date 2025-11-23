from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import UserDetails, BusinessDetails, CustomerDetails


# ---------- USER DETAILS AS SEPARATE MODEL IN ADMIN ----------

@admin.register(UserDetails)
class UserDetailsAdmin(admin.ModelAdmin):
    list_display = ("user", "phone_number", "created_at")
    search_fields = ("user__username", "phone_number")
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Account", {
            "fields": ("user", "phone_number"),
        }),
        ("Meta", {
            "fields": ("created_at",),
        }),
    )


# ---------- BUSINESS DETAILS ADMIN ----------

@admin.register(BusinessDetails)
class BusinessDetailsAdmin(admin.ModelAdmin):
    list_display = (
        "business_id",
        "business_name",
        "business_location",
        "owner",
        "is_active",
        "created_at",
    )
    list_filter = ("business_location", "is_active")
    search_fields = ("business_name", "business_location", "owner__username")
    readonly_fields = ("created_at",)


# ---------- CUSTOMER DETAILS ADMIN ----------

@admin.register(CustomerDetails)
class CustomerDetailsAdmin(admin.ModelAdmin):
    list_display = (
        "cust_id",
        "cust_name",
        "business",
        "cust_contact_number",
        "cust_visit_purpose",
        "cust_walkin_date",
        "cust_clockin",
        "cust_clockout",
    )
    list_filter = ("business", "cust_visit_purpose", "cust_walkin_date")
    search_fields = ("cust_name", "cust_contact_number", "business__business_name")
    readonly_fields = ("created_at",)


# ---------- INLINE USER DETAILS UNDER DJANGO USER ----------

class UserDetailsInline(admin.StackedInline):
    model = UserDetails
    can_delete = False
    verbose_name_plural = "WalkIn+ details"
    fk_name = "user"
    extra = 0  # don't show extra empty inline rows


class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserDetailsInline,)


# Replace default User admin with custom one that includes inline profile
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
