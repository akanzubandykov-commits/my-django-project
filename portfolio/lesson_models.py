from django.db import models


class Lesson(models.Model):
    LANGS = [("kk", "Қазақша"), ("ru", "Русский"), ("en", "English")]
    DESIGNS = [("dala", "Дала: қызыл және алтын"), ("teniz", "Теңіз: жасыл"),
               ("kara", "Қараңғы"), ("ak", "Қарапайым ақ"), ("magic", "Сиқыр: түнгі аспан")]

    teacher = models.ForeignKey("portfolio.Teacher", on_delete=models.CASCADE, related_name="lessons")
    subject = models.CharField("Пән", max_length=100)
    grade = models.PositiveSmallIntegerField("Сынып")
    language = models.CharField("Тіл", max_length=2, choices=LANGS, default="kk")
    topic = models.CharField("Тақырып", max_length=200)
    duration = models.PositiveSmallIntegerField("Ұзақтығы (мин)", default=45)
    design = models.CharField("Дизайн", max_length=10, choices=DESIGNS, default="dala")
    wishes = models.TextField("ЖИ-ге тілектер", blank=True)
    content = models.JSONField("Мазмұны", default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name, verbose_name_plural = "Сабақ", "Сабақтар"

    @property
    def display_title(self):
        return (self.content or {}).get("title") or self.topic

    def __str__(self):
        return self.display_title


class AIUsage(models.Model):
    """Мұғалімнің айына ЖИ-ге жіберген сұраныс саны (шек пен кейінгі жазылым үшін)."""
    teacher = models.ForeignKey("portfolio.Teacher", on_delete=models.CASCADE, related_name="ai_usage")
    month = models.CharField(max_length=7)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("teacher", "month")]
