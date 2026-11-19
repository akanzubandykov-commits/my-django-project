from django.conf import settings
from django.db import models
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

POSITIONS = ["Пән мұғалімі", "Бастауыш сынып мұғалімі", "Тәрбиеші", "Психолог",
             "Әлеуметтік педагог", "Әдіскер", "Директордың орынбасары"]
QUALIFICATIONS = ["Санаты жоқ", "Педагог", "Педагог-модератор", "Педагог-сарапшы",
                  "Педагог-зерттеуші", "Педагог-шебер"]
EDUCATIONS = ["Орта арнаулы", "Жоғары", "Магистр", "PhD / ғылым кандидаты"]
AS_CHOICES = lambda items: [(i, i) for i in items]


class School(models.Model):
    name = models.CharField("Мектеп", max_length=200)
    district = models.CharField("Аудан / қала", max_length=100, blank=True)

    class Meta:
        ordering = ["district", "name"]
        unique_together = [("name", "district")]
        verbose_name, verbose_name_plural = "Мектеп", "Мектептер"

    @staticmethod
    def ranking():
        """Мектептер рейтингі: мұғалім басына орташа расталған ұпай (тек мұғалімі бар мектептер)."""
        qs = School.objects.annotate(
            n=Count("teacher", distinct=True),
            total=Coalesce(Sum("teacher__submissions__points", filter=Q(teacher__submissions__status="approved")), 0),
        ).filter(n__gt=0)
        rows = [{"school": s, "name": s.name, "district": s.district, "n": s.n, "total": s.total,
                 "avg": round(s.total / s.n, 1)} for s in qs]
        rows.sort(key=lambda r: (-r["avg"], -r["total"], r["name"]))
        return rows

    def __str__(self):
        return f"{self.name} ({self.district})" if self.district else self.name


class Teacher(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    school = models.ForeignKey(School, on_delete=models.PROTECT, verbose_name="Мектеп")
    # Әр адам мұғалім; әкімші пен директор рөлдері оған ҚОСЫМША беріледі (екеуі де бір уақытта болуы мүмкін)
    is_zavuch = models.BooleanField("Әкімші (тексеруші)", default=False)
    is_director = models.BooleanField("Директор", default=False)
    middle_name = models.CharField("Әкесінің аты", max_length=100, blank=True)
    birth_date = models.DateField("Туған күні")
    phone = models.CharField("Телефон", max_length=30, blank=True)
    position = models.CharField("Лауазымы", max_length=100, choices=AS_CHOICES(POSITIONS))
    subject = models.CharField("Пәні", max_length=100)
    qualification = models.CharField("Біліктілік санаты", max_length=50, choices=AS_CHOICES(QUALIFICATIONS))
    experience = models.PositiveSmallIntegerField("Жұмыс өтілі (жыл)")
    education = models.CharField("Білімі", max_length=50, choices=AS_CHOICES(EDUCATIONS))

    class Meta:
        verbose_name, verbose_name_plural = "Мұғалім", "Мұғалімдер"

    @property
    def full_name(self):
        return " ".join(p for p in (self.user.last_name, self.user.first_name, self.middle_name) if p)

    @property
    def short_name(self):
        ini = "".join(f"{p[0]}." for p in (self.user.first_name, self.middle_name) if p)
        return f"{self.user.last_name} {ini}".strip()

    @property
    def can_review(self):
        return self.is_zavuch or self.is_director

    @property
    def roles_display(self):
        return ", ".join(["Мұғалім"] + (["Әкімші"] if self.is_zavuch else []) + (["Директор"] if self.is_director else []))

    def total_points(self):
        return self.submissions.filter(status=Submission.Status.APPROVED).aggregate(
            s=Coalesce(Sum("points"), 0))["s"]

    @staticmethod
    def school_ranking(school):
        """Мектеп бойынша рейтинг: тек расталған жазбалар ұпайы."""
        return (Teacher.objects.filter(school=school).select_related("user")
                .annotate(score=Coalesce(Sum("submissions__points",
                          filter=Q(submissions__status="approved")), 0))
                .order_by("-score", "user__last_name"))

    def __str__(self):
        return self.full_name


def role_upload_path(instance, filename):
    return f"roles/{instance.teacher_id}/{timezone.now():%Y%m}/{filename}"


class RoleRequest(models.Model):
    """Әкімші / директор рөлін сұрау. Рөл әкімші құжатты тексеріп растағанда ғана беріледі."""
    class Status(models.TextChoices):
        PENDING = "pending", "Күтуде"
        APPROVED = "approved", "Расталды"
        REJECTED = "rejected", "Қабылданбады"

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="role_requests")
    want_zavuch = models.BooleanField("Әкімші", default=False)
    want_director = models.BooleanField("Директор", default=False)
    document = models.FileField("Растайтын құжат (тағайындау бұйрығы)", upload_to=role_upload_path)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    comment = models.CharField(max_length=300, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name, verbose_name_plural = "Рөл сұранысы", "Рөл сұраныстары"

    @property
    def wanted_display(self):
        return ", ".join((["Әкімші"] if self.want_zavuch else []) + (["Директор"] if self.want_director else []))

    def review(self, user, approve, comment=""):
        self.status = self.Status.APPROVED if approve else self.Status.REJECTED
        self.comment, self.reviewed_by, self.reviewed_at = comment[:300], user, timezone.now()
        self.save()
        if approve:
            t = self.teacher
            t.is_zavuch = t.is_zavuch or self.want_zavuch
            t.is_director = t.is_director or self.want_director
            t.save(update_fields=["is_zavuch", "is_director"])

    def __str__(self):
        return f"{self.teacher}: {self.wanted_display}"


class Category(models.Model):
    name = models.CharField("Атауы", max_length=200)
    slug = models.SlugField(unique=True)
    icon = models.CharField("Иконка (i1…i11)", max_length=4, default="i1")
    group = models.CharField("Топ", max_length=5, choices=[("main", "Негізгі бағыттар"), ("extra", "Қосымша бағыттар")], default="main")
    order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField("Қысқаша түсініктеме (басты бетте көрсетіледі)", blank=True)

    class Meta:
        ordering = ["order"]
        verbose_name, verbose_name_plural = "Санат", "Санаттар"

    def __str__(self):
        return self.name


class Criterion(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="criteria")
    title = models.CharField("Критерий / деңгей", max_length=200)
    points = models.PositiveSmallIntegerField("Ұпай")

    class Meta:
        ordering = ["category__order", "points"]
        verbose_name, verbose_name_plural = "Критерий", "Критерийлер"

    def __str__(self):
        return f"{self.title} ({self.points} ұпай)"


def upload_path(instance, filename):
    return f"docs/{instance.teacher_id}/{timezone.now():%Y%m}/{filename}"


class Submission(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Күтуде"
        APPROVED = "approved", "Расталды"
        REJECTED = "rejected", "Қабылданбады"

    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name="submissions")
    criterion = models.ForeignKey(Criterion, on_delete=models.PROTECT, related_name="submissions")
    title = models.CharField("Атауы", max_length=250)
    event_date = models.DateField("Күні")
    description = models.TextField("Сипаттама", blank=True)
    document = models.FileField("Құжат (грамота, сертификат)", upload_to=upload_path)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    points = models.PositiveSmallIntegerField(default=0)
    reviewer_comment = models.CharField(max_length=300, blank=True)
    reviewed_by = models.ForeignKey(Teacher, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name, verbose_name_plural = "Жазба", "Жазбалар"

    def review(self, reviewer, approve, comment=""):
        self.status = self.Status.APPROVED if approve else self.Status.REJECTED
        self.points = self.criterion.points if approve else 0
        self.reviewer_comment, self.reviewed_by, self.reviewed_at = comment[:300], reviewer, timezone.now()
        self.save()

    def __str__(self):
        return self.title
from .lesson_models import AIUsage, Lesson  # noqa: E402,F401
