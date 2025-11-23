from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.db.models import Q
from datetime import timedelta
from django.http import HttpResponse
from django.urls import reverse
import csv
from .models import UserDetails, BusinessDetails, CustomerDetails


def mainpage(request):
    return render(request, "mainpage.html")


def signup_page(request):
    error = None
    success = None
    form_data = {
        "owner_name": "",
        "username": "",
        "email": "",
        "phone": "",
    }

    if request.method == "POST":
        owner_name = request.POST.get("owner_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")

        # Preserve values in case of error
        form_data = {
            "owner_name": owner_name,
            "username": username,
            "email": email,
            "phone": phone,
        }

        # Basic validations
        if password != confirm_password:
            error = "Passwords do not match."
        elif len(password) < 6:
            error = "Password should be at least 6 characters long."
        elif User.objects.filter(username=username).exists():
            error = "This username is already taken. Please choose another."
        elif User.objects.filter(email=email).exists():
            error = "This email is already registered."
        elif UserDetails.objects.filter(phone_number=phone).exists():
            error = "This mobile number is already registered."
        else:
            try:
                # Create Django auth user
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                )
                # Store owner/admin name in first_name (simple for now)
                user.first_name = owner_name
                user.save()

                # Create user_details record
                UserDetails.objects.create(
                    user=user,
                    phone_number=phone,
                )

                success = "Account created successfully. You can now log in."
                # Clear form on success
                form_data = {
                    "owner_name": "",
                    "username": "",
                    "email": "",
                    "phone": "",
                }

            except Exception:
                error = "Something went wrong while creating your account. Please try again."

    context = {
        "error": error,
        "success": success,
        "form": form_data,
    }
    return render(request, "signup_page.html", context)


def login_page(request):
    error = None
    success = None

    if request.method == "POST":

        # 1) PASSWORD RESET FLOW (from modal)
        if request.POST.get("reset_action") == "1":
            reset_method = request.POST.get("reset_method")  # 'email' or 'phone'
            identifier = request.POST.get("identifier", "").strip().lower()
            otp = request.POST.get("otp", "").strip()
            new_password = request.POST.get("new_password", "")
            confirm_password = request.POST.get("confirm_password", "")

            # Demo OTP check
            if otp != "123456":
                error = "Invalid OTP. Please try again."
            elif new_password != confirm_password:
                error = "Passwords do not match."
            elif len(new_password) < 6:
                error = "Password should be at least 6 characters long."
            else:
                user = None

                if reset_method == "email":
                    user = User.objects.filter(email=identifier).first()
                elif reset_method == "phone":
                    details = UserDetails.objects.filter(
                        phone_number=identifier
                    ).select_related("user").first()
                    if details:
                        user = details.user

                if not user:
                    error = "No account found with those details. Please sign up."
                else:
                    user.set_password(new_password)
                    user.save()
                    success = "Password reset successful. You can now log in with your new password."

        # 2) NORMAL LOGIN FLOW
        else:
            email = request.POST.get("email")
            phone = request.POST.get("phone")
            username = request.POST.get("username")
            password = request.POST.get("password", "")

            user = None

            # Determine login identity
            if email:
                user = User.objects.filter(email=email.strip().lower()).first()
            elif phone:
                details = UserDetails.objects.filter(
                    phone_number=phone.strip()
                ).select_related("user").first()
                if details:
                    user = details.user
            elif username:
                user = User.objects.filter(username=username.strip()).first()

            if not user:
                error = "No account found. Please sign up to continue."
            else:
                auth_user = authenticate(
                    request,
                    username=user.username,
                    password=password
                )
                if auth_user is None:
                    error = "Invalid credentials. Please try again."
                else:
                    # Log in and redirect to home
                    login(request, auth_user)
                    request.session["user_name"] = auth_user.first_name or auth_user.username
                    return redirect("home")

    return render(request, "login_page.html", {"error": error, "success": success})


@login_required
def home(request):
    # If somehow user hits /home/ without logging in
    if not request.user.is_authenticated:
        return redirect("loginpage")  # your URL name for login

    active_businesses = BusinessDetails.objects.filter(
        owner=request.user,
        is_active=True
    )

    has_active_business = active_businesses.exists()

    # Use session name if set, else fallback to first_name/username
    user_name = (
        request.session.get("user_name")
        or request.user.first_name
        or request.user.username
    )

    context = {
        "user_name": user_name,
        "has_active_business": has_active_business,
        "active_businesses": active_businesses,
    }
    return render(request, "home.html", context)

@login_required
def patient_dashboard(request):
    user = request.user

    # ─────────────────────────────
    # DETERMINE SELECTED BUSINESS
    # ─────────────────────────────
    active_businesses = BusinessDetails.objects.filter(
        owner=user,
        is_active=True
    )

    business_id = request.GET.get("business_id")
    selected_business = None

    if business_id:
        try:
            selected_business = active_businesses.get(pk=business_id)
        except BusinessDetails.DoesNotExist:
            # fallback to first active if invalid id
            selected_business = active_businesses.first()
    else:
        # default: first active business
        selected_business = active_businesses.first()

    if not selected_business:
        messages.error(
            request,
            "Please add and activate a business in Management → Add Business before using the Walk-In dashboard."
        )
        return redirect("management_dashboard")

    # Base URL with the selected business id (used in redirects)
    base_url = reverse("patient_dashboard") + f"?business_id={selected_business.business_id}"

    # ─────────────────────────────
    # CLOCK-OUT HANDLER
    # ─────────────────────────────
    if request.method == "POST" and request.POST.get("action") == "clockout":
        visit_id = request.POST.get("visit_id")

        try:
            visit = CustomerDetails.objects.get(
                pk=visit_id,
                user=user,
                business=selected_business,   # ensure it belongs to this business
                cust_clockout__isnull=True,  # only open visits
            )
            visit.cust_clockout = timezone.localtime().time()
            visit.save()

            messages.success(request, "Clock-out recorded.")
        except CustomerDetails.DoesNotExist:
            messages.error(request, "Visit not found or already clocked out.")

        return redirect(base_url)

    # ─────────────────────────────
    # NEW WALK-IN HANDLER
    # ─────────────────────────────
    if request.method == "POST" and request.POST.get("action") == "new_walkin":
        phone = request.POST.get("phone", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        dob_raw = request.POST.get("dob") or None
        care_of = request.POST.get("care_of", "").strip()
        relation = request.POST.get("relation", "").strip()
        purpose = request.POST.get("purpose", "").strip()
        notes = request.POST.get("notes", "").strip()

        if not phone or not first_name:
            messages.error(request, "Phone and first name are required.")
            return redirect(base_url)

        today = timezone.localdate()
        now_time = timezone.localtime().time()

        # IMPORTANT: store with this specific business
        CustomerDetails.objects.create(
            user=user,
            business=selected_business,
            cust_name=f"{first_name} {last_name}".strip(),
            cust_dob=dob_raw,
            cust_contact_number=phone,
            cust_companion=care_of,
            cust_companion_relation=relation,
            cust_visit_purpose=purpose,
            cust_notes=notes,
            cust_walkin_date=today,
            cust_clockin=now_time,
            # cust_clockout NULL until clock out
        )

        messages.success(request, "Walk-in registered successfully.")
        return redirect(base_url)

    # ─────────────────────────────
    # PAGE LOAD (GET) – SHOW OPEN VISITS FOR THIS BUSINESS
    # ─────────────────────────────
    today = timezone.localdate()

    visits = CustomerDetails.objects.filter(
        user=user,
        business=selected_business,            # only this business
        cust_walkin_date=today,
        cust_clockout__isnull=True,           # only pending
    ).order_by("cust_clockin")

    today_date = today.strftime("%d %b %Y")

    context = {
        "visits": visits,
        "today_date": today_date,
        "selected_business_name": selected_business.business_name,
    }
    return render(request, "patient_dashboard.html", context)

@login_required
def management_dashboard(request):
    user = request.user

    # Which tab is active? (used for staying on same section)
    active_tab = request.GET.get("tab", "overview")

    # ---------- HANDLE POST ACTIONS ----------
    if request.method == "POST":
        form_type = request.POST.get("form_type", "")
        tab_after = request.POST.get("tab", "overview")

        # Preserve business_id in redirect if provided
        business_id_param = request.POST.get("business_id", "")
        redirect_url = reverse("management_dashboard") + f"?tab={tab_after}"
        if business_id_param:
            redirect_url += f"&business_id={business_id_param}"

        # 1) ADD BUSINESS
        if form_type == "add_business":
            business_name = request.POST.get("business_name", "").strip()
            location = request.POST.get("location", "").strip()
            logo = request.POST.get("business_logo", "").strip()

            if business_name and location:
                BusinessDetails.objects.create(
                    owner=user,
                    business_name=business_name,
                    business_location=location,
                    business_logo=logo,
                    is_active=True,  # new businesses active by default
                )
            return redirect(redirect_url)

        # 2) UPDATE PROFILE (username, name, email, phone, password)
        elif form_type == "update_profile":
            new_username = request.POST.get("username", "").strip()
            display_name = request.POST.get("display_name", "").strip()
            email = request.POST.get("email", "").strip()
            phone = request.POST.get("phone", "").strip()
            new_password = request.POST.get("password", "").strip()

            # Update auth user fields
            if new_username and new_username != user.username:
                user.username = new_username
            if email:
                user.email = email
            if display_name:
                user.first_name = display_name
            user.save()

            # Ensure UserDetails exists
            try:
                details = user.details
            except UserDetails.DoesNotExist:
                details = UserDetails(user=user)
            if phone:
                details.phone_number = phone
            details.save()

            # If a new password is provided, change it
            if new_password:
                user.set_password(new_password)
                user.save()
                # They will need to log in again after password change.

            return redirect(redirect_url)

        # 3) UPDATE BUSINESS (name, location, logo, active/inactive)
        elif form_type == "update_business":
            business_id = request.POST.get("business_id")
            business = get_object_or_404(BusinessDetails, pk=business_id, owner=user)

            business_name = request.POST.get("business_name", "").strip()
            location = request.POST.get("location", "").strip()
            logo = request.POST.get("business_logo", "").strip()
            status = request.POST.get("status", "active")

            if business_name:
                business.business_name = business_name
            if location:
                business.business_location = location
            business.business_logo = logo
            business.is_active = (status == "active")
            business.save()

            return redirect(redirect_url)

    # ---------- BUILD CONTEXT FOR GET / PAGE RENDER ----------

    # User details
    try:
        details = user.details
        phone_number = details.phone_number
        # Placeholder for "password updated"
        password_updated_at = details.created_at.strftime("%b %Y")
    except UserDetails.DoesNotExist:
        details = None
        phone_number = ""
        password_updated_at = "N/A"

    display_name = user.first_name or user.get_username()

    # All businesses for this user (for selectors, tables, etc.)
    business_objs = BusinessDetails.objects.filter(owner=user).order_by("created_at")

    # Which business is selected?
    selected_business_id = request.GET.get("business_id")
    selected_business = None

    if business_objs.exists():
        if selected_business_id:
            try:
                # IMPORTANT: pk is your primary key (business_id)
                selected_business = business_objs.get(pk=selected_business_id)
            except BusinessDetails.DoesNotExist:
                selected_business = business_objs.first()
        else:
            selected_business = business_objs.first()
    else:
        selected_business = None

    # Build list for template with is_selected flag
    businesses = []
    for b in business_objs:
        businesses.append({
            "id": b.pk,  # use pk consistently
            "name": b.business_name,
            "location": b.business_location,
            "logo": b.business_logo,
            "customer_dashboard_enabled": b.is_active,
            "is_selected": bool(selected_business and b.pk == selected_business.pk),
        })

    # ---------- BASE QUERYSET: ONLY THIS USER + SELECTED BUSINESS ----------
    if selected_business:
        customers_qs = CustomerDetails.objects.filter(
            user=user,
            business=selected_business,  # strictly this business only
        )
    else:
        # No business yet → no data → all stats 0
        customers_qs = CustomerDetails.objects.none()

    # ---------- OVERVIEW STATS (PER SELECTED BUSINESS) ----------

    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    if selected_business:
        # Already filtered by user + business
        today_walkins = customers_qs.filter(cust_walkin_date=today).count()
        week_walkins = customers_qs.filter(
            cust_walkin_date__gte=week_start, cust_walkin_date__lte=today
        ).count()
        month_walkins = customers_qs.filter(
            cust_walkin_date__gte=month_start, cust_walkin_date__lte=today
        ).count()

        # ✅ CURRENT WALK-INS = today's visits that are still open
        current_pending_walkins = customers_qs.filter(
            cust_walkin_date=today,
            cust_clockout__isnull=True,
        ).count()

        total_walkins = customers_qs.count()

        last_30_start = today - timedelta(days=29)
        last_30_total = customers_qs.filter(
            cust_walkin_date__gte=last_30_start, cust_walkin_date__lte=today
        ).count()
        avg_per_day = round(last_30_total / 30, 1) if last_30_total else 0
    else:
        # No business selected -> hard zero everywhere
        today_walkins = 0
        week_walkins = 0
        month_walkins = 0
        current_pending_walkins = 0
        total_walkins = 0
        avg_per_day = 0

    # ---------- FILTERS FOR REPORTS (ALSO PER SELECTED BUSINESS) ----------

    from_date_str = request.GET.get("from_date", "").strip()
    to_date_str = request.GET.get("to_date", "").strip()
    time_from_str = request.GET.get("time_from", "").strip()
    time_to_str = request.GET.get("time_to", "").strip()
    search_query = request.GET.get("search", "").strip()

    from_date = parse_date(from_date_str) if from_date_str else None
    to_date = parse_date(to_date_str) if to_date_str else None
    time_from = parse_time(time_from_str) if time_from_str else None
    time_to = parse_time(time_to_str) if time_to_str else None

    # normalize dates – if only one provided, use it for both
    if from_date and not to_date:
        to_date = from_date
    if to_date and not from_date:
        from_date = to_date

    filtered_qs = customers_qs

    if from_date and to_date:
        filtered_qs = filtered_qs.filter(
            cust_walkin_date__gte=from_date,
            cust_walkin_date__lte=to_date,
        )

        # Apply per-day time window if both time_from and time_to present
        if time_from and time_to:
            mid_days = Q(
                cust_walkin_date__gt=from_date,
                cust_walkin_date__lt=to_date
            )
            start_day = Q(
                cust_walkin_date=from_date,
                cust_clockin__gte=time_from
            )
            end_day = Q(
                cust_walkin_date=to_date,
                cust_clockin__lte=time_to
            )
            filtered_qs = filtered_qs.filter(mid_days | start_day | end_day)
        elif time_from and from_date == to_date:
            filtered_qs = filtered_qs.filter(cust_clockin__gte=time_from)
        elif time_to and from_date == to_date:
            filtered_qs = filtered_qs.filter(cust_clockin__lte=time_to)

    # Search in name / number / purpose
    if search_query:
        filtered_qs = filtered_qs.filter(
            Q(cust_name__icontains=search_query)
            | Q(cust_contact_number__icontains=search_query)
            | Q(cust_visit_purpose__icontains=search_query)
        )

    # ---------- EXPORT CSV (uses filtered queryset and selected business) ----------
    if request.GET.get("export") == "csv":
        return csv_export_walkins(filtered_qs)

    # Records for reports table (latest first; show max 200)
    total_records = filtered_qs.count()
    records = filtered_qs.order_by("-cust_walkin_date", "-cust_clockin")[:200]

    context = {
        # which tab to highlight
        "active_tab": active_tab,

        # business selection
        "businesses": businesses,
        "selected_business_id": selected_business.pk if selected_business else "",
        "selected_business_name": selected_business.business_name if selected_business else "",

        # overview stats (per selected business)
        "today_walkins": today_walkins,
        "week_walkins": week_walkins,
        "month_walkins": month_walkins,
        "current_pending_walkins": current_pending_walkins,  # ✅ now only today's open visits
        "total_walkins": total_walkins,
        "avg_per_day": avg_per_day,  # ✅ only for selected business

        # reports
        "records": records,
        "total_records": total_records,
        "from_date": from_date_str,
        "to_date": to_date_str,
        "time_from": time_from_str,
        "time_to": time_to_str,
        "search": search_query,

        # profile
        "username": user.username,
        "display_name": display_name,
        "email": user.email,
        "phone": phone_number,
        "password_updated_at": password_updated_at,

        # pricing
        "current_plan_name": "Starter Pack – Monthly",
        "current_plan_price": 49,
    }

    return render(request, "management_dashboard.html", context)




def csv_export_walkins(qs):
    """
    Export walk-in records in CSV format according to the given queryset.
    This queryset is already filtered by selected business + filters.
    """
    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="walkins.csv"'},
    )

    writer = csv.writer(response)
    writer.writerow([
        "Customer Name",
        "Customer DOB",
        "Purpose",
        "Walk-in Date",
        "In Time",
        "Out Time",
        "Contact Number",
        "Companion",
        "Relation",
        "Notes",
    ])

    for r in qs.order_by("cust_walkin_date", "cust_clockin"):
        writer.writerow([
            r.cust_name or "",
            r.cust_dob or "",
            r.cust_visit_purpose or "",
            r.cust_walkin_date or "",
            r.cust_clockin or "",
            r.cust_clockout or "",
            r.cust_contact_number or "",
            r.cust_companion or "",
            r.cust_companion_relation or "",
            (r.cust_notes or "").replace("\n", " "),
        ])

    return response

