from django.shortcuts import render


def privacy_policy(request):
    return render(request, 'places/legal/privacy.html')


def terms_of_use(request):
    return render(request, 'places/legal/terms.html')


def support_requests(request):
    return render(request, 'places/legal/support_requests.html')
