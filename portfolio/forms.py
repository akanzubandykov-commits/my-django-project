import secrets
from datetime import date

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from django.db import transaction

from .models import (EDUCATIONS, POSITIONS, QUALIFICATIONS, RoleRequest, School, Submission, Teacher, AS_CHOICES)

User = get_user_model()
BLANK = [("", "Таңдаңыз")]
DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def check_doc(f):
    if not f.name.lower().endswith((".pdf", ".jpg", ".jpeg", ".png")):
        raise forms.ValidationError("Тек PDF, JPG немесе PNG.")
    if f.size > 10 * 1024 * 1024:
        raise forms.ValidationError("Файл 10 МБ-тан аспауы керек.")
    return f


class RegisterForm(forms.Form):
    wide = ["school", "want_zavuch", "want_director", "role_document"]
    last_name = forms.CharField(label="Тегі", max_length=150)
    first_name = forms.CharField(label="Аты", max_length=150)
    middle_name = forms.CharField(label="Әкесінің аты", max_length=100, required=False)
    birth_date = forms.DateField(label="Туған күні", widget=DATE)
    phone = forms.CharField(label="Телефон", max_length=30, required=False)
    email = forms.EmailField(label="Email")
    school = forms.ChoiceField(label="Мектеп")
    position = forms.ChoiceField(label="Лауазымы", choices=BLANK + AS_CHOICES(POSITIONS))
    subject = forms.CharField(label="Пәні", max_length=100)
    qualification = forms.ChoiceField(label="Біліктілік санаты", choices=BLANK + AS_CHOICES(QUALIFICATIONS))
    experience = forms.IntegerField(label="Жұмыс өтілі (жыл)", min_value=0, max_value=60)
    education = forms.ChoiceField(label="Білімі", choices=BLANK + AS_CHOICES(EDUCATIONS))
    want_zavuch = forms.BooleanField(label="Мен мектеп әкімшісімін (директордың орынбасары). Мұғалім болып қала беремін", required=False)
    want_director = forms.BooleanField(label="Мен мектеп директорымын (мұғалім болып қала беремін)", required=False)
    role_document = forms.FileField(label="Тағайындау бұйрығы немесе растайтын құжат", required=False,
                                    help_text="Әкімші/директор болсаңыз ғана. Сайт әкімшісі құжатты тексермейінше бұл рөл белсенді болмайды, ал мұғалім ретінде бірден жұмыс істей бересіз.")
    username = forms.CharField(label="Логин", min_length=3, max_length=150,
                               validators=[RegexValidator(r"^[A-Za-z0-9_.-]+$", "Тек латын әріптері, сандар, _ . -")])
    password1 = forms.CharField(label="Құпиясөз", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Құпиясөзді қайталаңыз", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        groups = {}
        for s in School.objects.all():
            groups.setdefault(s.district or "Басқа", []).append((str(s.pk), s.name))
        self.fields["school"].choices = BLANK + [(d, items) for d, items in groups.items()]

    def clean_school(self):
        try:
            return School.objects.get(pk=self.cleaned_data["school"])
        except (School.DoesNotExist, ValueError):
            raise forms.ValidationError("Тізімнен мектепті таңдаңыз.")

    def clean_birth_date(self):
        d = self.cleaned_data["birth_date"]
        if d >= date.today() or d.year < 1930:
            raise forms.ValidationError("Туған күні дұрыс емес.")
        return d

    def clean_email(self):
        e = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=e).exists():
            raise forms.ValidationError("Бұл email-мен тіркелген аккаунт бар. Құпиясөзді ұмытсаңыз, «Құпиясөзді ұмыттым» сілтемесін қолданыңыз.")
        return e

    def clean_username(self):
        u = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=u).exists():
            raise forms.ValidationError("Бұл логин бұрыннан бар.")
        return u

    def clean_role_document(self):
        f = self.cleaned_data.get("role_document")
        return check_doc(f) if f else f

    def clean(self):
        d = super().clean()
        if (d.get("want_zavuch") or d.get("want_director")) and not d.get("role_document") and "role_document" not in self.errors:
            self.add_error("role_document", "Әкімші/директор рөлін растау үшін құжат жүктеңіз.")
        p1, p2 = d.get("password1"), d.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Құпиясөздер сәйкес келмейді.")
            else:
                try:
                    validate_password(p1)
                except forms.ValidationError as e:
                    self.add_error("password1", e)
        return d

    @transaction.atomic
    def save(self):
        d = self.cleaned_data
        user = User.objects.create_user(d["username"], d["email"], d["password1"],
                                        first_name=d["first_name"], last_name=d["last_name"])
        school = d["school"]
        teacher = Teacher.objects.create(
            user=user, school=school, middle_name=d["middle_name"], birth_date=d["birth_date"],
            phone=d["phone"], position=d["position"], subject=d["subject"],
            qualification=d["qualification"], experience=d["experience"], education=d["education"])
        if (d["want_zavuch"] or d["want_director"]) and d["role_document"]:
            RoleRequest.objects.create(teacher=teacher, want_zavuch=d["want_zavuch"],
                                       want_director=d["want_director"], document=d["role_document"])
        return teacher


class SubmissionForm(forms.ModelForm):
    wide = ["title", "description", "document"]

    class Meta:
        model = Submission
        fields = ["criterion", "title", "event_date", "description", "document"]
        labels = {"criterion": "Деңгейі / критерий", "title": "Атауы", "event_date": "Күні",
                  "description": "Сипаттама", "document": "Құжат (PDF, JPG, PNG; 10 МБ-қа дейін)"}
        widgets = {"event_date": DATE, "description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, category, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["criterion"].queryset = category.criteria.all()
        self.fields["criterion"].empty_label = "Таңдаңыз"

    def clean_event_date(self):
        d = self.cleaned_data["event_date"]
        if d > date.today():
            raise forms.ValidationError("Болашақ күнді көрсетуге болмайды.")
        return d

    def clean_document(self):
        f = self.cleaned_data["document"]
        if not f.name.lower().endswith((".pdf", ".jpg", ".jpeg", ".png")):
            raise forms.ValidationError("Тек PDF, JPG немесе PNG.")
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Файл 10 МБ-тан аспауы керек.")
        return f


class RoleRequestForm(forms.ModelForm):
    wide = ["want_zavuch", "want_director", "document"]

    class Meta:
        model = RoleRequest
        fields = ["want_zavuch", "want_director", "document"]
        labels = {"want_zavuch": "Мен мектеп әкімшісімін (директордың орынбасары)", "want_director": "Мен мектеп директорымын",
                  "document": "Тағайындау бұйрығы немесе растайтын құжат (PDF, JPG, PNG)"}

    def __init__(self, *args, teacher, **kwargs):
        super().__init__(*args, **kwargs)
        if teacher.is_zavuch:
            del self.fields["want_zavuch"]
        if teacher.is_director:
            del self.fields["want_director"]

    def clean_document(self):
        return check_doc(self.cleaned_data["document"])

    def clean(self):
        d = super().clean()
        if not (d.get("want_zavuch") or d.get("want_director")):
            raise forms.ValidationError("Кемінде бір рөлді таңдаңыз.")
        return d


class TeacherAddForm(RegisterForm):
    """Әкімші (superuser) немесе мектеп әкімшісі (директор/әкімші) мұғалімді өзі қосады."""
    want_zavuch = want_director = role_document = password1 = password2 = None  # тіркеу өрістері алынып тасталды
    wide = []
    password = forms.CharField(label="Құпиясөз (бос қалдырсаңыз, автоматты жасалады)", required=False,
                               widget=forms.PasswordInput(render_value=False))
    is_zavuch = forms.BooleanField(label="Әкімші (директордың орынбасары)", required=False)
    is_director = forms.BooleanField(label="Директор", required=False)

    def __init__(self, *args, school=None, allow_roles=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.school = school
        if school is not None:
            del self.fields["school"]
        if not allow_roles:
            del self.fields["is_zavuch"], self.fields["is_director"]

    def clean_password(self):
        p = self.cleaned_data.get("password")
        if p:
            validate_password(p)
        return p

    @transaction.atomic
    def save(self):
        d = self.cleaned_data
        pw = d.get("password") or secrets.token_urlsafe(9)
        user = User.objects.create_user(d["username"], d["email"], pw,
                                        first_name=d["first_name"], last_name=d["last_name"])
        teacher = Teacher.objects.create(
            user=user, school=self.school or d["school"], middle_name=d["middle_name"], birth_date=d["birth_date"],
            phone=d["phone"], position=d["position"], subject=d["subject"], qualification=d["qualification"],
            experience=d["experience"], education=d["education"],
            is_zavuch=bool(d.get("is_zavuch")), is_director=bool(d.get("is_director")))
        return teacher, pw
