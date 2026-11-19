import csv

from django.core.management.base import BaseCommand, CommandError

from portfolio.models import School


class Command(BaseCommand):
    help = "Мектептер тізімін файлдан жүктейді. Әр жол: Мектеп атауы;Аудан (аудан міндетті емес)"

    def add_arguments(self, parser):
        parser.add_argument("path", help="UTF-8 кодтауындағы .txt немесе .csv файл")

    def handle(self, path, **opts):
        try:
            f = open(path, encoding="utf-8-sig", newline="")
        except OSError as e:
            raise CommandError(e)
        added = 0
        with f:
            for row in csv.reader(f, delimiter=";"):
                if not row or not row[0].strip():
                    continue
                name = " ".join(row[0].split())
                district = " ".join(row[1].split()) if len(row) > 1 else ""
                _, new = School.objects.get_or_create(name=name, district=district)
                added += new
        self.stdout.write(self.style.SUCCESS(f"Қосылды: {added}"))
