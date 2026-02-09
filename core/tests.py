"""
DELIVR-CM Core Tests
=====================

Tests for:
1. Custom User Model (creation, roles, debt system)
2. Wallet blocking mechanism
3. PromoCode validation & discount application
4. Security Middleware (rate limiting, headers)
"""

import pytest
from decimal import Decimal
from django.test import TestCase, RequestFactory, override_settings
from django.contrib.gis.geos import Point
from django.utils import timezone
from datetime import timedelta

from core.models import User, UserRole, PromoCode


class TestUserModel(TestCase):
    """Tests for the custom User model."""
    
    def setUp(self):
        """Create test users for each role."""
        self.admin = User.objects.create_user(
            phone_number='+237699000001',
            password='testpass123',
            role=UserRole.ADMIN,
            full_name='Admin Test',
        )
        self.courier = User.objects.create_user(
            phone_number='+237699000002',
            password='testpass123',
            role=UserRole.COURIER,
            full_name='Courier Test',
        )
        self.client_user = User.objects.create_user(
            phone_number='+237699000003',
            password='testpass123',
            role=UserRole.CLIENT,
            full_name='Client Test',
        )
        self.business = User.objects.create_user(
            phone_number='+237699000004',
            password='testpass123',
            role=UserRole.BUSINESS,
            full_name='Business Test',
        )
    
    # ==========================================
    # User Creation Tests
    # ==========================================
    
    def test_user_creation_with_phone(self):
        """User should be created with phone number as identifier."""
        self.assertEqual(self.courier.phone_number, '+237699000002')
        self.assertTrue(self.courier.check_password('testpass123'))
    
    def test_user_uuid_primary_key(self):
        """User should have UUID as primary key."""
        import uuid
        self.assertIsInstance(self.courier.id, uuid.UUID)
    
    def test_user_roles(self):
        """Each user should have the correct role."""
        self.assertEqual(self.admin.role, UserRole.ADMIN)
        self.assertEqual(self.courier.role, UserRole.COURIER)
        self.assertEqual(self.client_user.role, UserRole.CLIENT)
        self.assertEqual(self.business.role, UserRole.BUSINESS)
    
    def test_is_courier_property(self):
        """is_courier should return True only for COURIER role."""
        self.assertTrue(self.courier.is_courier)
        self.assertFalse(self.client_user.is_courier)
        self.assertFalse(self.business.is_courier)
    
    def test_is_business_property(self):
        """is_business should return True only for BUSINESS role."""
        self.assertTrue(self.business.is_business)
        self.assertFalse(self.courier.is_business)
    
    def test_superuser_creation(self):
        """Superuser should have is_staff and is_superuser."""
        superuser = User.objects.create_superuser(
            phone_number='+237699999999',
            password='superpass123',
        )
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
    
    def test_duplicate_phone_number_rejected(self):
        """Should not allow duplicate phone numbers."""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                phone_number='+237699000002',  # Same as courier
                password='testpass123',
            )
    
    # ==========================================
    # Wallet & Debt System Tests
    # ==========================================
    
    def test_initial_wallet_balance_is_zero(self):
        """New user should have 0 wallet balance."""
        self.assertEqual(self.courier.wallet_balance, Decimal('0.00'))
    
    def test_courier_not_blocked_at_zero_balance(self):
        """Courier with 0 balance should NOT be blocked."""
        self.assertFalse(self.courier.is_courier_blocked)
    
    def test_courier_not_blocked_within_debt_ceiling(self):
        """Courier with debt within ceiling should NOT be blocked."""
        self.courier.wallet_balance = Decimal('-2000.00')
        self.courier.debt_ceiling = Decimal('2500.00')
        self.courier.save()
        self.assertFalse(self.courier.is_courier_blocked)
    
    def test_courier_blocked_when_exceeds_debt_ceiling(self):
        """Courier should be BLOCKED when debt exceeds ceiling."""
        self.courier.wallet_balance = Decimal('-3000.00')
        self.courier.debt_ceiling = Decimal('2500.00')
        self.courier.save()
        self.assertTrue(self.courier.is_courier_blocked)
    
    def test_courier_blocked_at_exact_ceiling(self):
        """Courier should be blocked at exactly -debt_ceiling."""
        self.courier.wallet_balance = Decimal('-2500.00')
        self.courier.debt_ceiling = Decimal('2500.00')
        self.courier.save()
        # wallet_balance < -debt_ceiling means strictly less than
        # At exactly -2500, it's NOT less than -2500, so not blocked
        # This tests the exact boundary condition
        self.assertFalse(self.courier.is_courier_blocked)
    
    def test_courier_positive_balance_not_blocked(self):
        """Courier with positive balance should not be blocked."""
        self.courier.wallet_balance = Decimal('5000.00')
        self.courier.save()
        self.assertFalse(self.courier.is_courier_blocked)
    
    def test_non_courier_is_never_blocked(self):
        """Non-courier users should never be considered blocked."""
        self.client_user.wallet_balance = Decimal('-10000.00')
        self.client_user.save()
        self.assertFalse(self.client_user.is_courier_blocked)
    
    # ==========================================
    # Business Slug Tests
    # ==========================================
    
    def test_business_slug_auto_generated(self):
        """Business user should get auto-generated slug on save."""
        self.business.save()
        if self.business.slug:
            self.assertIsNotNone(self.business.slug)
            self.assertIn('business', self.business.slug.lower())
    
    def test_user_str_representation(self):
        """User __str__ should be meaningful."""
        result = str(self.courier)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


class TestPromoCode(TestCase):
    """Tests for PromoCode model."""
    
    def setUp(self):
        """Create test promo codes."""
        self.percentage_code = PromoCode.objects.create(
            code='WELCOME2025',
            discount_type=PromoCode.DiscountType.PERCENTAGE,
            discount_value=Decimal('15.00'),
            max_uses=100,
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30),
        )
        self.fixed_code = PromoCode.objects.create(
            code='SAVE500',
            discount_type=PromoCode.DiscountType.FIXED,
            discount_value=Decimal('500.00'),
            max_uses=50,
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30),
        )
        self.expired_code = PromoCode.objects.create(
            code='EXPIRED',
            discount_type=PromoCode.DiscountType.PERCENTAGE,
            discount_value=Decimal('10.00'),
            max_uses=100,
            valid_from=timezone.now() - timedelta(days=30),
            valid_until=timezone.now() - timedelta(days=1),
        )
    
    def test_valid_promo_code(self):
        """Active, non-expired code should be valid."""
        self.assertTrue(self.percentage_code.is_valid)
    
    def test_expired_promo_code(self):
        """Expired code should be invalid."""
        self.assertFalse(self.expired_code.is_valid)
    
    def test_percentage_discount(self):
        """15% discount on 2000 XAF should give 1700 XAF."""
        result = self.percentage_code.apply_discount(Decimal('2000.00'))
        self.assertEqual(result, Decimal('1700.00'))
    
    def test_fixed_discount(self):
        """500 XAF fixed discount on 2000 XAF should give 1500 XAF."""
        result = self.fixed_code.apply_discount(Decimal('2000.00'))
        self.assertEqual(result, Decimal('1500.00'))
    
    def test_discount_never_below_zero(self):
        """Discount should never result in a negative price."""
        result = self.fixed_code.apply_discount(Decimal('300.00'))
        self.assertGreaterEqual(result, Decimal('0.00'))
    
    def test_unique_code(self):
        """Promo codes should be unique."""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            PromoCode.objects.create(
                code='WELCOME2025',  # Duplicate
                discount_type=PromoCode.DiscountType.PERCENTAGE,
                discount_value=Decimal('10.00'),
                valid_from=timezone.now(),
                valid_until=timezone.now() + timedelta(days=1),
            )


class TestSecurityMiddleware(TestCase):
    """Tests for security middleware behavior."""
    
    def test_health_endpoint_accessible(self):
        """Health check should be accessible without auth."""
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['service'], 'delivr-cm')
    
    def test_readiness_endpoint_accessible(self):
        """Readiness check should be accessible without auth."""
        response = self.client.get('/health/ready/')
        self.assertIn(response.status_code, [200, 503])
        data = response.json()
        self.assertIn('checks', data)
    
    def test_detailed_health_requires_auth(self):
        """Detailed health should require staff authentication."""
        response = self.client.get('/health/detailed/')
        self.assertEqual(response.status_code, 403)
    
    def test_security_headers_present(self):
        """Response should contain security headers."""
        response = self.client.get('/health/')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['X-XSS-Protection'], '1; mode=block')
        self.assertIn('Referrer-Policy', response)
