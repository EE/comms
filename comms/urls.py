"""
URL configuration for comms project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
from django.http import HttpResponse
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

from .api import extra_urls, router


urlpatterns = [
    path('robots.txt', lambda r: HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")),
    path('admin/', admin.site.urls),

    # API routes
    path('api/', include(router.urls)),
    path('api/', include(extra_urls)),

    # Postmark webhooks
    path('postmark/', include('postmark.urls')),
]
