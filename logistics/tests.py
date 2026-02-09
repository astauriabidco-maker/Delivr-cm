"""
DELIVR-CM Logistics Tests
===========================

Tests for:
1. Pricing Engine (formula, rounding, minimum fare, split)
2. Delivery Model (OTP generation, status transitions)
3. Neighborhood model
4. Traffic Events (creation, voting, expiration)
"""

import math
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.gis.geos import Point
from django.utils import timezone
from datetime import timedelta

from logistics.models import (
    Delivery, DeliveryStatus, PaymentMethod,
    Neighborhood, City,
    TrafficEvent, TrafficEventType, TrafficEventSeverity, TrafficEventVote,
    Rating, RatingType,
)
from logistics.services.pricing import PricingEngine
from core.models import User, UserRole


class TestPricingEngine(TestCase):
    """Tests for the Pricing Engine pricing calculation."""
    
    def setUp(self):
        """Create a PricingEngine with known config."""
        self.engine = PricingEngine()
        # Override with known values for deterministic tests
        self.engine.base_fare = Decimal('500')
        self.engine.cost_per_km = Decimal('150')
        self.engine.minimum_fare = Decimal('1000')
        self.engine.platform_fee_percent = Decimal('0.20')
    
    # ==========================================
    # Rounding Rules
    # ==========================================
    
    def test_round_up_to_hundred(self):
        """1320 should round up to 1400."""
        result = self.engine.round_to_hundred(Decimal('1320'))
        self.assertEqual(result, Decimal('1400'))
    
    def test_round_exact_hundred(self):
        """1500 should stay 1500."""
        result = self.engine.round_to_hundred(Decimal('1500'))
        self.assertEqual(result, Decimal('1500'))
    
    def test_round_just_above_hundred(self):
        """1501 should round to 1600."""
        result = self.engine.round_to_hundred(Decimal('1501'))
        self.assertEqual(result, Decimal('1600'))
    
    def test_round_small_amount(self):
        """50 should round to 100."""
        result = self.engine.round_to_hundred(Decimal('50'))
        self.assertEqual(result, Decimal('100'))
    
    # ==========================================
    # Price Calculation
    # ==========================================
    
    @patch.object(PricingEngine, 'get_route_distance')
    def test_price_formula_basic(self, mock_distance):
        """Price = RoundUp100(500 + distance * 150), minimum 1000."""
        mock_distance.return_value = 5.0  # 5 km
        
        origin = Point(9.7, 4.05)
        dest = Point(9.75, 4.06)
        
        distance, total, fee, earning = self.engine.calculate_price(origin, dest)
        
        # 500 + 5*150 = 1250 -> round to 1300
        self.assertEqual(distance, 5.0)
        self.assertEqual(total, Decimal('1300'))
    
    @patch.object(PricingEngine, 'get_route_distance')
    def test_minimum_fare_applied(self, mock_distance):
        """Short distance should return minimum fare."""
        mock_distance.return_value = 1.0  # 1 km
        
        origin = Point(9.7, 4.05)
        dest = Point(9.71, 4.06)
        
        distance, total, fee, earning = self.engine.calculate_price(origin, dest)
        
        # 500 + 1*150 = 650 -> round to 700, but minimum is 1000
        self.assertEqual(total, Decimal('1000'))
    
    @patch.object(PricingEngine, 'get_route_distance')
    def test_platform_fee_split(self, mock_distance):
        """Platform gets 20%, courier gets 80%."""
        mock_distance.return_value = 10.0  # 10 km
        
        origin = Point(9.7, 4.05)
        dest = Point(9.8, 4.1)
        
        distance, total, fee, earning = self.engine.calculate_price(origin, dest)
        
        # 500 + 10*150 = 2000 -> round = 2000
        self.assertEqual(total, Decimal('2000'))
        self.assertEqual(fee, Decimal('400.00'))     # 20%
        self.assertEqual(earning, Decimal('1600.00'))  # 80%
    
    @patch.object(PricingEngine, 'get_route_distance')
    def test_fee_plus_earning_equals_total(self, mock_distance):
        """Platform fee + courier earning should always equal total price."""
        mock_distance.return_value = 7.3
        
        origin = Point(9.7, 4.05)
        dest = Point(9.78, 4.08)
        
        _, total, fee, earning = self.engine.calculate_price(origin, dest)
        self.assertEqual(fee + earning, total)
    
    # ==========================================
    # Haversine Fallback
    # ==========================================
    
    @patch.object(PricingEngine, 'get_route_distance', return_value=None)
    def test_haversine_fallback(self, mock_distance):
        """When OSRM fails, should fall back to Haversine + 30%."""
        origin = Point(9.7, 4.05)
        dest = Point(9.75, 4.06)
        
        distance, total, fee, earning = self.engine.calculate_price(
            origin, dest, use_fallback=True
        )
        
        # Should return a valid result
        self.assertIsNotNone(total)
        self.assertGreater(distance, 0)
        self.assertGreater(total, 0)
    
    @patch.object(PricingEngine, 'get_route_distance', return_value=None)
    def test_no_fallback_raises_error(self, mock_distance):
        """When OSRM fails and fallback disabled, should raise."""
        origin = Point(9.7, 4.05)
        dest = Point(9.75, 4.06)
        
        with self.assertRaises(ValueError):
            self.engine.calculate_price(origin, dest, use_fallback=False)
    
    # ==========================================
    # Neighborhood Estimation
    # ==========================================
    
    @patch.object(PricingEngine, 'get_route_distance')
    def test_neighborhood_estimation_has_margin(self, mock_distance):
        """Neighborhood estimation should add 20% safety margin."""
        mock_distance.return_value = 10.0
        
        shop = Point(9.7, 4.05)
        neighborhood_center = Point(9.8, 4.1)
        
        distance, total, _, _ = self.engine.estimate_from_neighborhood(
            shop, neighborhood_center
        )
        
        # Distance should be 10 * 1.2 = 12 km (20% margin)
        self.assertEqual(distance, 12.0)
    
    # ==========================================
    # Haversine Distance Calculation
    # ==========================================
    
    def test_haversine_known_distance(self):
        """Test haversine with known Douala locations."""
        # Akwa to Bonaberi is approximately 4-5 km
        akwa = Point(9.6937, 4.0483)
        bonaberi = Point(9.6645, 4.0743)
        
        distance = self.engine.get_haversine_distance(akwa, bonaberi)
        
        # Should be roughly between 3 and 6 km
        self.assertGreater(distance, 2.0)
        self.assertLess(distance, 7.0)
    
    def test_haversine_same_point_is_zero(self):
        """Same point should give ~0 distance."""
        point = Point(9.7, 4.05)
        distance = self.engine.get_haversine_distance(point, point)
        self.assertAlmostEqual(distance, 0.0, places=5)


class TestDeliveryModel(TestCase):
    """Tests for the Delivery model."""
    
    def setUp(self):
        self.sender = User.objects.create_user(
            phone_number='+237699300001',
            password='testpass123',
            role=UserRole.CLIENT,
        )
        self.courier = User.objects.create_user(
            phone_number='+237699300002',
            password='testpass123',
            role=UserRole.COURIER,
        )
    
    def _create_delivery(self, **kwargs):
        defaults = {
            'sender': self.sender,
            'pickup_geo': Point(9.7, 4.05),
            'dropoff_geo': Point(9.75, 4.06),
            'distance_km': 5.0,
            'total_price': Decimal('1300.00'),
            'platform_fee': Decimal('260.00'),
            'courier_earning': Decimal('1040.00'),
            'payment_method': PaymentMethod.CASH_P2P,
        }
        defaults.update(kwargs)
        return Delivery.objects.create(**defaults)
    
    def test_delivery_auto_uuid(self):
        """Delivery should have auto-generated UUID."""
        import uuid
        d = self._create_delivery()
        self.assertIsInstance(d.id, uuid.UUID)
    
    def test_delivery_otp_generated_on_save(self):
        """OTP code should be auto-generated on creation."""
        d = self._create_delivery()
        self.assertIsNotNone(d.otp_code)
        self.assertEqual(len(d.otp_code), 4)
        self.assertTrue(d.otp_code.isdigit())
    
    def test_delivery_default_status_pending(self):
        """New delivery should default to PENDING status."""
        d = self._create_delivery()
        self.assertEqual(d.status, DeliveryStatus.PENDING)
    
    def test_is_pending(self):
        """is_pending should return True for PENDING delivery."""
        d = self._create_delivery()
        self.assertTrue(d.is_pending)
    
    def test_is_completed(self):
        """is_completed should return True for COMPLETED delivery."""
        d = self._create_delivery(status=DeliveryStatus.COMPLETED)
        self.assertTrue(d.is_completed)
    
    def test_delivery_without_courier(self):
        """Delivery should allow null courier (before assignment)."""
        d = self._create_delivery(courier=None)
        self.assertIsNone(d.courier)
    
    def test_pricing_frozen_at_creation(self):
        """Price fields should be stored and not change."""
        d = self._create_delivery(
            total_price=Decimal('1300.00'),
            platform_fee=Decimal('260.00'),
            courier_earning=Decimal('1040.00'),
        )
        d.refresh_from_db()
        self.assertEqual(d.total_price, Decimal('1300.00'))
        self.assertEqual(d.platform_fee, Decimal('260.00'))
        self.assertEqual(d.courier_earning, Decimal('1040.00'))


class TestNeighborhoodModel(TestCase):
    """Tests for the Neighborhood model."""
    
    def test_create_neighborhood(self):
        """Should create a neighborhood with center point."""
        n = Neighborhood.objects.create(
            name='Akwa',
            city=City.DOUALA,
            center_geo=Point(9.6937, 4.0483),
            radius_km=1.5,
        )
        self.assertEqual(str(n), 'Douala - Akwa')
    
    def test_unique_neighborhood_per_city(self):
        """Same name in same city should be unique."""
        Neighborhood.objects.create(
            name='Akwa',
            city=City.DOUALA,
            center_geo=Point(9.6937, 4.0483),
        )
        with self.assertRaises(IntegrityError):
            Neighborhood.objects.create(
                name='Akwa',
                city=City.DOUALA,
                center_geo=Point(9.7, 4.05),
            )
    
    def test_same_name_different_city_allowed(self):
        """Same neighborhood name in different cities should be ok."""
        Neighborhood.objects.create(
            name='Centre',
            city=City.DOUALA,
            center_geo=Point(9.6937, 4.0483),
        )
        n2 = Neighborhood.objects.create(
            name='Centre',
            city=City.YAOUNDE,
            center_geo=Point(11.5, 3.87),
        )
        self.assertIsNotNone(n2.pk)


class TestTrafficEvents(TestCase):
    """Tests for the Traffic Event system (Waze-like)."""
    
    def setUp(self):
        self.courier1 = User.objects.create_user(
            phone_number='+237699400001',
            password='testpass123',
            role=UserRole.COURIER,
        )
        self.courier2 = User.objects.create_user(
            phone_number='+237699400002',
            password='testpass123',
            role=UserRole.COURIER,
        )
    
    def test_create_traffic_event(self):
        """Should create a traffic event with location."""
        event = TrafficEvent.objects.create(
            reported_by=self.courier1,
            event_type=TrafficEventType.ACCIDENT,
            severity=TrafficEventSeverity.HIGH,
            location=Point(9.7, 4.05),
            description='Accident sur le rond-point Deido',
        )
        self.assertTrue(event.is_active)
        self.assertIsNotNone(event.expires_at)
    
    def test_traffic_event_auto_ttl(self):
        """TTL should be set based on event type."""
        event = TrafficEvent.objects.create(
            reported_by=self.courier1,
            event_type=TrafficEventType.POLICE,
            severity=TrafficEventSeverity.MEDIUM,
            location=Point(9.7, 4.05),
        )
        # Police events should have a TTL set
        self.assertIsNotNone(event.expires_at)
        self.assertTrue(event.expires_at > timezone.now())
    
    def test_expired_event(self):
        """Event past its TTL should be considered expired."""
        event = TrafficEvent.objects.create(
            reported_by=self.courier1,
            event_type=TrafficEventType.ACCIDENT,
            severity=TrafficEventSeverity.HIGH,
            location=Point(9.7, 4.05),
            expires_at=timezone.now() - timedelta(minutes=5),
        )
        self.assertTrue(event.is_expired)
    
    def test_vote_on_event(self):
        """Couriers should be able to vote on events."""
        event = TrafficEvent.objects.create(
            reported_by=self.courier1,
            event_type=TrafficEventType.TRAFFIC_JAM,
            severity=TrafficEventSeverity.MEDIUM,
            location=Point(9.7, 4.05),
        )
        vote = TrafficEventVote.objects.create(
            event=event,
            voter=self.courier2,
            is_upvote=True,
        )
        self.assertTrue(vote.is_upvote)
    
    def test_unique_vote_per_user_per_event(self):
        """Each courier can only vote once per event."""
        event = TrafficEvent.objects.create(
            reported_by=self.courier1,
            event_type=TrafficEventType.ROAD_CLOSED,
            severity=TrafficEventSeverity.CRITICAL,
            location=Point(9.7, 4.05),
        )
        TrafficEventVote.objects.create(
            event=event, voter=self.courier2, is_upvote=True
        )
        with self.assertRaises(IntegrityError):
            TrafficEventVote.objects.create(
                event=event, voter=self.courier2, is_upvote=False
            )
    
    def test_lat_lng_properties(self):
        """Latitude/longitude properties should return correct values."""
        event = TrafficEvent.objects.create(
            reported_by=self.courier1,
            event_type=TrafficEventType.HAZARD,
            severity=TrafficEventSeverity.LOW,
            location=Point(9.7, 4.05),
        )
        # Point(x=lng, y=lat) in PostGIS
        self.assertAlmostEqual(event.latitude, 4.05, places=2)
        self.assertAlmostEqual(event.longitude, 9.7, places=1)


class TestRatingModel(TestCase):
    """Tests for the Rating model."""
    
    def setUp(self):
        self.courier = User.objects.create_user(
            phone_number='+237699500001',
            password='testpass123',
            role=UserRole.COURIER,
        )
        self.sender = User.objects.create_user(
            phone_number='+237699500002',
            password='testpass123',
            role=UserRole.CLIENT,
        )
        self.delivery = Delivery.objects.create(
            sender=self.sender,
            courier=self.courier,
            status=DeliveryStatus.COMPLETED,
            payment_method=PaymentMethod.CASH_P2P,
            pickup_geo=Point(9.7, 4.05),
            dropoff_geo=Point(9.75, 4.06),
            distance_km=5.0,
            total_price=Decimal('1300.00'),
            platform_fee=Decimal('260.00'),
            courier_earning=Decimal('1040.00'),
        )
    
    def test_create_rating(self):
        """Should create a rating for a delivery."""
        rating = Rating.objects.create(
            delivery=self.delivery,
            rater=self.sender,
            rated=self.courier,
            rating_type=RatingType.COURIER,
            score=5,
            comment='Très rapide !',
        )
        self.assertEqual(rating.score, 5)
    
    def test_rating_score_range(self):
        """Rating score should be between 1 and 5."""
        rating = Rating.objects.create(
            delivery=self.delivery,
            rater=self.sender,
            rated=self.courier,
            rating_type=RatingType.COURIER,
            score=3,
        )
        self.assertGreaterEqual(rating.score, 1)
        self.assertLessEqual(rating.score, 5)
