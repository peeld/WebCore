from django.urls import path

from .views import HealthCheckView, UserAddressView

app_name = 'core_app'

urlpatterns = [
    path('health/',  HealthCheckView.as_view(), name='health'),
    path('address/', UserAddressView.as_view(), name='address'),
]
