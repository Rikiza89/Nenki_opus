from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/people/', views.people_list, name='people_list'),
    path('api/people/<int:pk>/', views.person_detail, name='person_detail'),
    path('api/import/preview/', views.import_preview, name='import_preview'),
    path('api/import/confirm/', views.import_confirm, name='import_confirm'),
    path('api/calculate/', views.calculate, name='calculate'),
    path('api/generate/word/', views.generate_word, name='generate_word'),
    path('api/generate/pdf/', views.generate_pdf, name='generate_pdf'),
]
