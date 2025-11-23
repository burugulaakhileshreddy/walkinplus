from django.db import models
from django.contrib.auth.models import User


class UserDetails(models.Model):
    """
    Extra details for a Django auth User.
    Your user_details table:
    - username (via FK to auth.User)
    - phone_number
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="details"
    )
    phone_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Contact Number"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_details"

    def __str__(self):
        return f"{self.user.username} ({self.phone_number})"


class BusinessDetails(models.Model):
    """
    Business/clinic details for a user.
    business_details table:
    - owner (User)
    - business_id (auto, PK)
    - business_name
    - business_location
    - business_logo (string path/url for now)
    - is_active (to show/hide in dashboards)
    """

    # Auto-increment, unique business id (primary key)
    business_id = models.AutoField(primary_key=True)

    # Which Django user owns this business
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="businesses"
    )

    business_name = models.CharField(max_length=200)
    business_location = models.CharField(max_length=200)

    # For now, store logo as a simple text path or URL.
    business_logo = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional logo filename or URL"
    )

    # Active/inactive flag used on Home page & dashboards
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "business_details"

    def __str__(self):
        return f"{self.business_name} ({self.business_location})"


class CustomerDetails(models.Model):
    """
    Customer/patient details for a specific business.
    customer_details table:
    - user (owner/creator)
    - business (FK)
    - cust_id (auto, PK)
    - all the customer fields
    """

    # Auto-increment, unique customer id
    cust_id = models.AutoField(primary_key=True)

    # Who created/owns this customer (clinic user)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="customers"
    )

    # Which business this customer belongs to
    business = models.ForeignKey(
        BusinessDetails,
        on_delete=models.CASCADE,
        related_name="customers"
    )

    cust_name = models.CharField(max_length=150)
    cust_dob = models.DateField(null=True, blank=True)

    cust_contact_number = models.CharField(max_length=20)

    cust_companion = models.CharField(
        max_length=150,
        blank=True,
        help_text="Name of person accompanying the customer"
    )
    cust_companion_relation = models.CharField(
        max_length=100,
        blank=True,
        help_text="Relation of companion to the customer"
    )

    cust_visit_purpose = models.CharField(
        max_length=200,
        help_text="Purpose of visit (e.g., Fever, Checkup, Follow-up)"
    )

    cust_notes = models.TextField(
        blank=True,
        help_text="Additional notes about the visit"
    )

    # Walk-in date & times
    cust_walkin_date = models.DateField()
    cust_clockin = models.TimeField()
    cust_clockout = models.TimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customer_details"

    def __str__(self):
        return f"{self.cust_name} ({self.cust_contact_number})"
