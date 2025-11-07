from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
import uuid

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('staff', 'Staff'),
        ('manager', 'Manager'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    phone = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    
    class Meta:
        db_table = 'users'

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
    
    def __str__(self):
        return self.name

class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'suppliers'
    
    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True, editable=False, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], default=0)
    quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    reorder_level = models.IntegerField(default=10, validators=[MinValueValidator(0)]) #  It's the minimum quantity threshold that triggers a reorder alert
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'products'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    def save(self, *args, **kwargs):
        if not self.sku:
            # Generate SKU: PRD-XXXXXX (6 random characters)
            self.sku = f"PRD-{uuid.uuid4().hex[:6].upper()}"
            # Ensure uniqueness
            while Product.objects.filter(sku=self.sku).exists():
                self.sku = f"PRD-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)
    
    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level

class Sale(models.Model):
    invoice_number = models.CharField(max_length=50, unique=True)
    staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    customer_name = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=15, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, choices=[
        ('paid', 'Paid'),
        ('partial', 'Partial Payment'),
        ('unpaid', 'Unpaid')
    ], default='paid')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sales'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Invoice {self.invoice_number}"
    
    @property
    def is_debtor(self):
        return self.balance > 0

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'sale_items'
    
    def save(self, *args, **kwargs):
        self.total = (self.price * self.quantity) - self.discount
        super().save(*args, **kwargs)

class Payment(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=[
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('transfer', 'Bank Transfer'),
    ], default='cash')
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']

class StockMovement(models.Model):
    MOVEMENT_TYPES = [
        ('in', 'Stock In'),
        ('out', 'Stock Out'),
        ('adjustment', 'Adjustment'),
    ]
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField()
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'stock_movements'
        ordering = ['-created_at']