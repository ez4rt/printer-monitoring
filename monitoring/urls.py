from . import views
from django.urls import path
from django.conf.urls import handler404, handler400, handler403
from .views import CustomErrorView

app_name = 'monitoring'

handler400 = CustomErrorView.as_view()
handler403 = CustomErrorView.as_view()
handler404 = CustomErrorView.as_view()

urlpatterns = [
 path('', views.index, name='index'),
 path('<int:printer_id>', views.single_printer, name='printer'),
 path('reports', views.reports, name='reports'),
 path('report/<str:nm_report>/<str:qty_days>', views.single_report, name='report'),
 path('export_report/', views.export_report, name='export_report'),
 path('data-in-js/<str:nm_data>', views.data_in_js, name='data_in_js'),
 path('events', views.events, name='events'),
 path('forecast', views.forecast, name='forecast'),
]



