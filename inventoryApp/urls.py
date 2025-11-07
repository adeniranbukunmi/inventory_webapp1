from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Home/POS
    path('home/', views.home, name='home'),
    path('api/search-products/', views.search_products, name='search_products'),
    path('api/process-sale/', views.process_sale, name='process_sale'),
    path('receipt/<int:sale_id>/', views.view_receipt, name='view_receipt'),
    path('receipt/<int:sale_id>/edit/', views.edit_receipt, name='edit_receipt'),
    
    # Admin
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # Staff Management
    path('register_staff/', views.register_staff, name='register_staff'),
    path('staff/', views.staff_list, name='staff_list'),
    
    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.add_product, name='add_product'),
    path('products/edit/<int:pk>/', views.edit_product, name='edit_product'),
    path('products/delete/<int:pk>/', views.delete_product, name='delete_product'),
    
    # Debtors
    path('debtors/', views.debtors_list, name='debtors_list'),
    path('debtors/payment/<int:sale_id>/', views.record_payment, name='record_payment'),
    path('debtors/history/<int:sale_id>/', views.debtor_payment_history, name='debtor_payment_history'),
    path('receipt/<int:sale_id>/edit/', views.edit_receipt, name='edit_receipt')
]