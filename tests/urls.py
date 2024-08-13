import allianceauth.urls
from django.urls import path

from . import views

urlpatterns = allianceauth.urls.urlpatterns

urlpatterns += [
    # Navhelper test urls
    url(r'^main-page/$', views.page, name='p1'),
    url(r'^main-page/sub-section/$', views.page, name='p1-s1'),
    url(r'^second-page/$', views.page, name='p1'),
]
