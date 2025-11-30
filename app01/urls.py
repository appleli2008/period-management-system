from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('period/login/', views.period_login, name='period_login'),
    path('period/register/', views.period_register, name='period_register'),
    path('period/logout/', views.period_logout, name='period_logout'),
    path('period/set-profile/', views.set_profile, name='set_profile'),
    path('period/set-profile-ajax/', views.set_profile_ajax, name='set_profile_ajax'),
    path('period/start/', views.add_period_start, name='add_period_start'),
    path('period/end/', views.add_period_end, name='add_period_end'),
    path('period/info/', views.get_period_info, name='get_period_info'),
    path('period/adjust/', views.adjust_period, name='adjust_period'),
    path('period/predictions/', views.get_prediction_info, name='get_prediction_info'),  # 新增
    path('period/delete/<int:record_id>/', views.delete_period, name='delete_period'),
    path('period/edit/', views.period_edit, name='period_edit'),
    path('period/delete-account/', views.period_delete, name='period_delete'),

]