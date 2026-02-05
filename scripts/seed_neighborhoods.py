"""
Seed script for neighborhoods in Douala and Yaoundé
"""
from django.contrib.gis.geos import Point
from logistics.models import Neighborhood

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
]

def run():
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
            print(f'✅ Créé: {name} (Douala)')
    
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
            print(f'✅ Créé: {name} (Yaoundé)')
    
    print(f'\n📍 Total créés: {created_count} quartiers')
    print(f'📍 Total en base: {Neighborhood.objects.count()} quartiers')

if __name__ == '__main__':
    run()
