"""
Django management command to seed neighborhoods for Douala and Yaoundé.

Usage:
    docker-compose exec -T web python manage.py seed_neighborhoods
"""
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from logistics.models import Neighborhood


class Command(BaseCommand):
    help = 'Seed neighborhoods for Douala and Yaoundé'

    def handle(self, *args, **options):
        # Quartiers de Douala
        quartiers_douala = [
            ('Akwa', 4.0489, 9.7067),
            ('Bonanjo', 4.0260, 9.6999),
            ('Bonapriso', 4.0218, 9.6880),
            ('Deido', 4.0650, 9.7120),
            ('Bali', 4.0550, 9.7000),
            ('Ndokoti', 4.0420, 9.7450),
            ('Makepe', 4.0700, 9.7450),
            ('Bonamoussadi', 4.0850, 9.7350),
            ('Kotto', 4.0650, 9.7700),
            ('Logpom', 4.0920, 9.7480),
            ('New Bell', 4.0380, 9.7150),
            ('Bessengue', 4.0450, 9.7050),
            ('Bepanda', 4.0580, 9.7380),
            ('Yassa', 4.0150, 9.7850),
            ('PK8', 4.0050, 9.7950),
            ('PK10', 3.9950, 9.8050),
            ('PK12', 3.9850, 9.8150),
            ('PK14', 3.9750, 9.8250),
            ('Nyalla', 4.0020, 9.7650),
            ('Logbessou', 4.0980, 9.7550),
        ]

        # Quartiers de Yaoundé
        quartiers_yaounde = [
            ('Bastos', 3.8900, 11.5100),
            ('Nlongkak', 3.8750, 11.5150),
            ('Mvan', 3.8350, 11.5250),
            ('Essos', 3.8600, 11.5350),
            ('Messa', 3.8700, 11.4950),
            ('Biyem-Assi', 3.8450, 11.4750),
            ('Mokolo', 3.8650, 11.5080),
            ('Mendong', 3.8400, 11.4800),
            ('Mimboman', 3.8500, 11.5450),
            ('Mvog-Mbi', 3.8550, 11.5200),
            ('Briqueterie', 3.8680, 11.5120),
            ('Nkoldongo', 3.8620, 11.5380),
            ('Emana', 3.9050, 11.5250),
            ('Simbock', 3.8300, 11.4650),
            ('Nsam', 3.8400, 11.5100),
            ('Ekounou', 3.8550, 11.5500),
            ('Nkolbisson', 3.8650, 11.4550),
            ('Olembe', 3.9150, 11.5200),
            ('Ahala', 3.8200, 11.5050),
            ('Nkomo', 3.8150, 11.4900),
        ]

        created_count = 0

        for name, lat, lng in quartiers_douala:
            obj, created = Neighborhood.objects.get_or_create(
                name=name,
                city='Douala',
                defaults={
                    'center_geo': Point(lng, lat, srid=4326),
                    'radius_km': 2.0,
                    'is_active': True
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✅ Créé: {name} (Douala)'))
            else:
                self.stdout.write(f'⏭️  Existe: {name} (Douala)')

        for name, lat, lng in quartiers_yaounde:
            obj, created = Neighborhood.objects.get_or_create(
                name=name,
                city='Yaounde',
                defaults={
                    'center_geo': Point(lng, lat, srid=4326),
                    'radius_km': 2.0,
                    'is_active': True
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'✅ Créé: {name} (Yaoundé)'))
            else:
                self.stdout.write(f'⏭️  Existe: {name} (Yaoundé)')

        total = Neighborhood.objects.count()
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'📍 Total créés: {created_count} quartiers'))
        self.stdout.write(self.style.SUCCESS(f'📍 Total en base: {total} quartiers'))
