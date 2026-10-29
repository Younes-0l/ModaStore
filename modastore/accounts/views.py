from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .services import services
from .forms import AddressForm, OTPForm, PhoneForm, ProfileForm
from .models import Address


SESSION_PHONE_KEY = 'otp_phone'

# Create your views here.

def _safe_next(request):
    """Return the ?next= target only if it points to this site."""
    target = request.POST.get('next') or request.GET.get('next') or ''
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return ''


def login_view(request):
    if request.user.is_authenticated:
        return redirect('catalog:home')

    form = PhoneForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        phone = form.cleaned_data['phone_number']
        try:
            services.request_otp(phone)
        except services.OTPError as e:
            form.add_error(None, str(e))
        else:
            request.session[SESSION_PHONE_KEY] = phone
            url = reverse('accounts:verify')
            nxt = _safe_next(request)
            return redirect(f'{url}?next={nxt}' if nxt else url)

    return render(request, 'accounts/login.html', {'form': form, 'next': _safe_next(request)})


def verify_view(request):
    if request.user.is_authenticated:
        return redirect('catalog:home')

    phone = request.session.get(SESSION_PHONE_KEY)
    if not phone:
        return redirect('accounts:login')

    form = OTPForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            user = services.verify_otp(phone, form.cleaned_data['code'])
        except services.OTPError as e:
            form.add_error(None, str(e))
        else:
            request.session.pop(SESSION_PHONE_KEY, None)
            login(request, user)  # also rotates the session key
            if not user.first_name:
                messages.success(request, 'خوش آمدید! لطفاً اطلاعات پروفایل خود را کامل کنید.')
                return redirect('accounts:profile')
            return redirect(_safe_next(request) or 'catalog:home')

    return render(request, 'accounts/verify.html', {
        'form': form,
        'phone': phone,
        'wait': services.resend_wait_seconds(phone),
        'next': _safe_next(request),
    })


@require_POST
def resend_view(request):
    phone = request.session.get(SESSION_PHONE_KEY)
    if not phone:
        return redirect('accounts:login')
    try:
        services.request_otp(phone)
        messages.success(request, 'کد جدید ارسال شد.')
    except services.OTPError as e:
        messages.error(request, str(e))
    return redirect('accounts:verify')


@require_POST
def logout_view(request):
    # POST only: a GET logout can be triggered by any external link or image
    logout(request)
    return redirect('catalog:home')


@login_required
def profile_view(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'اطلاعات شما ذخیره شد.')
        return redirect('accounts:profile')
    return render(request, 'accounts/profile.html', {
        'form': form,
        'addresses': request.user.addresses.all(),
    })


@login_required
def address_create(request):
    form = AddressForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        address = form.save(commit=False)
        address.user = request.user
        _save_address(address)
        messages.success(request, 'آدرس اضافه شد.')
        return redirect('accounts:profile')
    return render(request, 'accounts/address_form.html', {'form': form, 'title': 'افزودن آدرس'})


@login_required
def address_edit(request, pk):
    # Filtering by user means other users' addresses return 404
    address = get_object_or_404(Address, pk=pk, user=request.user)
    form = AddressForm(request.POST or None, instance=address)
    if request.method == 'POST' and form.is_valid():
        _save_address(form.save(commit=False))
        messages.success(request, 'آدرس ویرایش شد.')
        return redirect('accounts:profile')
    return render(request, 'accounts/address_form.html', {'form': form, 'title': 'ویرایش آدرس'})


@login_required
@require_POST
def address_delete(request, pk):
    get_object_or_404(Address, pk=pk, user=request.user).delete()
    messages.success(request, 'آدرس حذف شد.')
    return redirect('accounts:profile')


def _save_address(address):
    """Keep exactly one default address; the first address becomes default."""
    from django.db import transaction

    with transaction.atomic():
        has_other = Address.objects.filter(user=address.user).exclude(pk=address.pk).exists()
        if not has_other:
            address.is_default = True
        if address.is_default:
            Address.objects.filter(user=address.user, is_default=True).exclude(
                pk=address.pk
            ).update(is_default=False)
        address.save()