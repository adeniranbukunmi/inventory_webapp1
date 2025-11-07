from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Sum, F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from .models import (User, Product, Supplier, Category, Sale, SaleItem, StockMovement, Payment)
from .forms import (StaffRegistrationForm, PaymentForm, ProductForm)
import json

def is_admin(user):
    return user.is_authenticated and (user.role == 'admin' or user.is_superuser)

def is_staff_or_admin(user):
    return user.is_authenticated and user.role in ['admin', 'staff', 'manager']

# Authentication Views
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'login.html')

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')

# Home/POS View
@login_required
@user_passes_test(is_staff_or_admin)
def home(request):
    return render(request, 'home.html')

# Product Search API
@login_required
def search_products(request):
    query = request.GET.get('q', '')
    if query:
        products = Product.objects.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query)
        )[:20]
        
        data = [{
            'id': p.id,
            'name': p.name,
            'sku': p.sku,
            'price': str(p.price),
            'quantity': p.quantity,
            'image': p.image.url if p.image else None
        } for p in products]
        
        return JsonResponse(data, safe=False)
    return JsonResponse([], safe=False)

# Process Sale
@login_required
def process_sale(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            items = data.get('items', [])
            customer_name = data.get('customer_name', '').strip()
            customer_phone = data.get('customer_phone', '').strip()
            amount_paid = Decimal(data.get('amount_paid', 0))
            
            if not items:
                return JsonResponse({'success': False, 'error': 'No items in cart'})
            
            # Validate customer information
            if not customer_name:
                return JsonResponse({'success': False, 'error': 'Customer name is required'})
            
            if not customer_phone:
                return JsonResponse({'success': False, 'error': 'Customer phone is required'})
            
            # Check stock availability for all items BEFORE processing
            for item in items:
                try:
                    product = Product.objects.get(id=item['product_id'])
                    if product.quantity == 0:
                        return JsonResponse({
                            'success': False,
                            'error': f'{product.name} is OUT OF STOCK'
                        })
                    if product.quantity < item['quantity']:
                        return JsonResponse({
                            'success': False, 
                            'error': f'{product.name} has insufficient stock. Available: {product.quantity}, Requested: {item["quantity"]}'
                        })
                except Product.DoesNotExist:
                    return JsonResponse({'success': False, 'error': 'Product not found'})
            
            # Generate invoice number
            last_sale = Sale.objects.order_by('-id').first()
            invoice_num = f"INV-{(last_sale.id + 1) if last_sale else 1:06d}"
            
            # Calculate totals
            subtotal = sum(Decimal(item['total']) + Decimal(item['discount']) for item in items)
            total_discount = sum(Decimal(item['discount']) for item in items)
            total = subtotal - total_discount
            balance = total - amount_paid
            
            # Determine payment status
            if balance <= 0:
                payment_status = 'paid'
                balance = 0
            elif amount_paid > 0:
                payment_status = 'partial'
            else:
                payment_status = 'unpaid'
            
            # Create sale
            sale = Sale.objects.create(
                invoice_number=invoice_num,
                staff=request.user,
                customer_name=customer_name,
                customer_phone=customer_phone,
                subtotal=subtotal,
                discount=total_discount,
                total=total,
                amount_paid=amount_paid,
                balance=balance,
                payment_status=payment_status
            )
            
            # Create sale items and update inventory
            for item in items:
                product = Product.objects.get(id=item['product_id'])
                
                SaleItem.objects.create(
                    sale=sale,
                    product=product,
                    product_name=product.name,
                    quantity=item['quantity'],
                    price=Decimal(item['price']),
                    discount=Decimal(item['discount']),
                    total=Decimal(item['total'])
                )
                
                # Update product quantity
                product.quantity -= item['quantity']
                product.save()
                
                # Record stock movement
                StockMovement.objects.create(
                    product=product,
                    movement_type='out',
                    quantity=-item['quantity'],
                    reference=invoice_num,
                    notes=f'Sale to {customer_name}',
                    created_by=request.user
                )
            
            # Record payment if any
            if amount_paid > 0:
                Payment.objects.create(
                    sale=sale,
                    amount=amount_paid,
                    payment_method='cash',
                    created_by=request.user
                )
            
            return JsonResponse({
                'success': True,
                'invoice_number': invoice_num,
                'sale_id': sale.id
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

# Admin Dashboard
@login_required
@user_passes_test(is_admin)
def admin_dashboard(request):
    total_products = Product.objects.count()
    low_stock_products = Product.objects.filter(quantity__lte=F('reorder_level')).count()
    total_sales = Sale.objects.count()
    total_revenue = Sale.objects.aggregate(Sum('total'))['total__sum'] or 0
    debtors_count = Sale.objects.filter(balance__gt=0).count()
    
    # Recent sales
    recent_sales = Sale.objects.select_related('staff').prefetch_related('items')[:10]
    
    # Low stock alert
    low_stock = Product.objects.filter(quantity__lte=F('reorder_level'))[:10]
    
    context = {
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'debtors_count': debtors_count,
        'recent_sales': recent_sales,
        'low_stock': low_stock,
    }
    return render(request, 'admin_dashboard.html', context)

# Staff Management
@login_required
@user_passes_test(is_admin)
def register_staff(request):
    if request.method == 'POST':
        form = StaffRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Staff {user.username} registered successfully!')
            return redirect('staff_list')
    else:
        form = StaffRegistrationForm()
    
    return render(request, 'register_staff.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def staff_list(request):
    staff = User.objects.all().order_by('-date_joined')
    return render(request, 'staff_list.html', {'staff': staff})

# Product Management
@login_required
@user_passes_test(is_admin)
def product_list(request):
    products = Product.objects.select_related('category', 'supplier').all()
    return render(request, 'product_list.html', {'products': products})

@login_required
@user_passes_test(is_admin)
def add_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Product {product.name} added successfully!')
            return redirect('product_list')
    else:
        form = ProductForm()
    
    return render(request, 'product_form.html', {'form': form, 'action': 'Add'})

@login_required
@user_passes_test(is_admin)
def edit_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f'Product {product.name} updated successfully!')
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'product_form.html', {'form': form, 'action': 'Edit'})

@login_required
@user_passes_test(is_admin)
def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted successfully!')
        return redirect('product_list')
    return render(request, 'product_confirm_delete.html', {'product': product})

# Debtor Management - NOW ACCESSIBLE TO STAFF
@login_required
@user_passes_test(is_staff_or_admin)
def debtors_list(request):
    debtors = Sale.objects.filter(balance__gt=0).select_related('staff').prefetch_related('payments').order_by('-created_at')
    return render(request, 'debtors_list.html', {'debtors': debtors})

@login_required
@user_passes_test(is_staff_or_admin)
def record_payment(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.sale = sale
            payment.created_by = request.user
            
            # Validate payment amount
            if payment.amount > sale.balance:
                messages.error(request, f'Payment amount (₦{payment.amount}) cannot exceed balance of ₦{sale.balance}')
                return render(request, 'record_payment.html', {'form': form, 'sale': sale})
            
            if payment.amount <= 0:
                messages.error(request, 'Payment amount must be greater than zero')
                return render(request, 'record_payment.html', {'form': form, 'sale': sale})
            
            payment.save()
            
            # Update sale balance
            sale.amount_paid += payment.amount
            sale.balance = sale.total - sale.amount_paid
            
            if sale.balance <= 0:
                sale.payment_status = 'paid'
                sale.balance = 0
            else:
                sale.payment_status = 'partial'
            
            sale.save()
            messages.success(request, f'Payment of ₦{payment.amount} recorded successfully!')
            return redirect('debtors_list')
    else:
        form = PaymentForm()
    
    return render(request, 'record_payment.html', {'form': form, 'sale': sale})

# New: Payment History View
@login_required
@user_passes_test(is_staff_or_admin)
def debtor_payment_history(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    payments = sale.payments.all().order_by('-created_at')
    
    context = {
        'sale': sale,
        'payments': payments,
    }
    return render(request, 'debtor_payment_history.html', context)

# Receipt Views
@login_required
def view_receipt(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, 'receipt.html', {'sale': sale})

# New: Edit Receipt View
@login_required
def edit_receipt(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    
    if request.method == 'POST':
        customer_name = request.POST.get('customer_name', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        
        if not customer_name:
            messages.error(request, 'Customer name is required')
            return render(request, 'edit_receipt.html', {'sale': sale})
        
        if not customer_phone:
            messages.error(request, 'Customer phone is required')
            return render(request, 'edit_receipt.html', {'sale': sale})
        
        sale.customer_name = customer_name
        sale.customer_phone = customer_phone
        sale.save()
        
        messages.success(request, 'Receipt updated successfully!')
        return redirect('view_receipt', sale_id=sale.id)
    
    return render(request, 'edit_receipt.html', {'sale': sale})