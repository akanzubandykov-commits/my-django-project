import secrets
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.core.mail import send_mail
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.db.models import ProtectedError
from django.utils.http import url_has_allowed_host_and_scheme
from django.db.models.functions import Coalesce
import csv

from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import RegisterForm, RoleRequestForm, SubmissionForm, TeacherAddForm
User = get_user_model()
from .models import Category, Criterion, RoleRequest, School, Submission, Teacher


def teacher_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *a, **k):
        t = getattr(request.user, "teacher", None)
        if t is None and request.user.is_staff:
            return redirect("panel")
        if t is None:
            messages.error(request, "Бұл тіркелгіде мұғалім профилі жоқ.")
            return redirect("home")
        request.teacher = t
        return view(request, *a, **k)
    return wrapper


def reviewer_required(view):
    @teacher_required
    @wraps(view)
    def wrapper(request, *a, **k):
        if not request.teacher.can_review:
            raise PermissionDenied
        return view(request, *a, **k)
    return wrapper


def home(request):
    top = [r for r in School.ranking() if r["total"] > 0][:5]
    for r in top:
        r["w"] = min(100, round(r["avg"] * 100 / max(top[0]["avg"], 0.1)))
    cats = Category.objects.prefetch_related("criteria")
    ctx = {"top": top, "cat_groups": [("Педагог, басшы және басшының орынбасары үшін", cats.filter(group="main")),
                                       ("Педагог үшін", cats.filter(group="extra")),
                                      ("Басшы / басшының орынбасары үшін", cats.filter(group="head"))]}
    t = getattr(request.user, "teacher", None) if request.user.is_authenticated else None
    if t:  # кірген мұғалім сайттың басты бетінде тек ӨЗ мектебінің мұғалімдерін көреді
        mine = list(Teacher.school_ranking(t.school)[:10])
        mx = max([x.score for x in mine] + [1])
        for x in mine:
            x.w, x.me = round(x.score * 100 / mx), x.pk == t.pk
        ctx.update(my_school=t.school, mine=mine)
    return render(request, "home.html", ctx)


def register(request):
    if request.user.is_authenticated:
        return redirect("cabinet")
    form = RegisterForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        teacher = form.save()
        login(request, teacher.user)
        u = teacher.user
        send_mail("Ustaz Portfolio: тіркелу сәтті өтті",
                  f"Сәлем, {u.first_name}!\n\nСіз Ustaz Portfolio сайтында тіркелдіңіз.\nЛогиніңіз: {u.username}\n\n"
                  "Құпиясөз қауіпсіздік үшін хатқа жазылмайды. Ұмытып қалсаңыз, кіру бетіндегі "
                  "«Құпиясөзді ұмыттым» сілтемесін басыңыз: сол email-ге логин мен жаңа құпиясөз жасау сілтемесі келеді.\n",
                  None, [u.email], fail_silently=True)
        return redirect("cabinet")
    return render(request, "register.html", {"form": form, "no_schools": not School.objects.exists()})


@teacher_required
def cabinet(request):
    """Басты бет: өз мектебінің мұғалімдер рейтингі + мектептер рейтингі (басқа мектептің мұғалімдері көрінбейді)."""
    t = request.teacher
    ranking = list(Teacher.school_ranking(t.school))
    schools = School.ranking()
    return render(request, "cabinet/home.html", {
        "t": t, "ranking": ranking, "total": t.total_points(), "count": len(ranking),
        "place": next((i for i, x in enumerate(ranking, 1) if x.pk == t.pk), None),
        "schools": schools, "my_school_id": t.school_id,
        "school_place": next((i for i, r in enumerate(schools, 1) if r["school"].pk == t.school_id), None),
        "req": t.role_requests.first()})


@teacher_required
def profile(request):
    t = request.teacher
    return render(request, "cabinet/profile.html", {"t": t, "req": t.role_requests.first()})


@teacher_required
def role_request(request):
    t = request.teacher
    pending = t.role_requests.filter(status="pending").first()
    have_all = t.is_zavuch and t.is_director
    form = None
    if not pending and not have_all:
        form = RoleRequestForm(request.POST or None, request.FILES or None, teacher=t)
        if request.method == "POST" and form.is_valid():
            r = form.save(commit=False)
            r.teacher = t
            r.save()
            messages.success(request, "Сұраныс жіберілді. Әкімші құжатты тексеріп, нәтижесін email-ге хабарлайды.")
            return redirect("cabinet")
    return render(request, "cabinet/role_request.html", {"form": form, "pending": pending, "have_all": have_all,
                                                         "history": t.role_requests.all()[:5]})


@login_required
def role_document(request, pk):
    r = get_object_or_404(RoleRequest, pk=pk)
    t = getattr(request.user, "teacher", None)
    if not (request.user.is_staff or (t and r.teacher_id == t.pk)):
        raise PermissionDenied
    return FileResponse(r.document.open("rb"))


@teacher_required
def enter(request):
    return render(request, "cabinet/enter.html", {
        "groups": [("Педагог, басшы және басшының орынбасары үшін", Category.objects.filter(group="main")),
                   ("Педагог үшін", Category.objects.filter(group="extra"))]
        + ([("Басшы / басшының орынбасары үшін", Category.objects.filter(group="head"))] if request.teacher.can_review else [])})


@teacher_required
def enter_form(request, slug):
    cat = get_object_or_404(Category, slug=slug)
    if cat.group == "head" and not request.teacher.can_review:
        raise PermissionDenied
    form = SubmissionForm(request.POST or None, request.FILES or None, category=cat)
    if request.method == "POST" and form.is_valid():
        s = form.save(commit=False)
        s.teacher = request.teacher
        s.save()
        messages.success(request, "Жазба жіберілді. Әкімші растағаннан кейін ұпай қосылады.")
        return redirect("records")
    return render(request, "cabinet/enter_form.html", {"cat": cat, "form": form})


@teacher_required
def records(request):
    return render(request, "cabinet/records.html", {
        "items": request.teacher.submissions.select_related("criterion__category")})


@teacher_required
@require_POST
def record_delete(request, pk):
    s = get_object_or_404(Submission, pk=pk, teacher=request.teacher, status=Submission.Status.PENDING)
    s.document.delete(save=False)
    s.delete()
    messages.success(request, "Жазба жойылды.")
    return redirect("records")


@teacher_required
def rating(request):
    t = request.teacher
    ranking = list(Teacher.school_ranking(t.school))
    place = next((i for i, x in enumerate(ranking, 1) if x.pk == t.pk), None)
    cats = list(Category.objects.filter(**({} if t.can_review else {"group__in": ["main", "extra"]})).annotate(pts=Coalesce(Sum(
        "criteria__submissions__points",
        filter=Q(criteria__submissions__teacher=t, criteria__submissions__status="approved")), 0)))
    top = max([c.pts for c in cats] + [1])
    for c in cats:
        c.w = round(c.pts * 100 / top)
    subs = t.submissions
    return render(request, "cabinet/rating.html", {
        "t": t, "total": t.total_points(), "place": place, "count": len(ranking), "cats": cats,
        "sent": subs.count(), "ok": subs.filter(status="approved").count(), "ranking": ranking[:10]})


@reviewer_required
def review(request):
    items = (Submission.objects.filter(teacher__school=request.teacher.school, status="pending")
             .exclude(teacher=request.teacher).select_related("teacher__user", "criterion__category"))
    return render(request, "cabinet/review.html", {"items": items})


@reviewer_required
@require_POST
def review_action(request, pk, action):
    if action not in ("approve", "reject"):
        raise Http404
    s = get_object_or_404(Submission, pk=pk, teacher__school=request.teacher.school, status="pending")
    if s.teacher_id == request.teacher.pk:
        raise PermissionDenied  # өз жазбасын растауға болмайды
    s.review(request.teacher, action == "approve", request.POST.get("comment", ""))
    messages.success(request, "Жазба расталды." if action == "approve" else "Жазба қабылданбады.")
    return redirect("review")


@login_required
def document(request, pk):
    s = get_object_or_404(Submission, pk=pk)
    t = getattr(request.user, "teacher", None)
    ok = request.user.is_staff or (t and (s.teacher_id == t.pk or (t.can_review and s.teacher.school_id == t.school_id)))
    if not ok:
        raise PermissionDenied
    return FileResponse(s.document.open("rb"))


def _report(school):
    """Мектеп есебі: мұғалім x санат кестесі (тек расталған жазбалар)."""
    cats = list(Category.objects.all())
    pts = {}
    for r in (Submission.objects.filter(teacher__school=school, status="approved")
              .values("teacher_id", "criterion__category_id").annotate(p=Sum("points"))):
        pts[(r["teacher_id"], r["criterion__category_id"])] = r["p"]
    rows = [{"pos": i, "t": t, "cells": [pts.get((t.pk, c.pk), 0) for c in cats]}
            for i, t in enumerate(Teacher.school_ranking(school), 1)]
    return cats, rows


@reviewer_required
def report(request):
    cats, rows = _report(request.teacher.school)
    return render(request, "cabinet/report.html", {"cats": list(enumerate(cats, 1)), "rows": rows,
                                                   "school": request.teacher.school})


def _safe(v):
    v = str(v)
    return "'" + v if v[:1] in ("=", "+", "-", "@") else v  # Excel формула инъекциясынан қорғау


@reviewer_required
def report_csv(request):
    school = request.teacher.school
    cats, rows = _report(school)
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="reiting.csv"'
    resp.write("\ufeff")  # Excel-де қазақ әріптері дұрыс ашылуы үшін
    w = csv.writer(resp, delimiter=";")
    w.writerow(["№", "Мұғалім", "Пәні", "Санаты", "Өтілі", "Жалпы ұпай"] + [_safe(c.name) for c in cats])
    for r in rows:
        t = r["t"]
        w.writerow([r["pos"], _safe(t.full_name), _safe(t.subject), t.qualification, t.experience, t.score] + r["cells"])
    return resp


# ================= Әкімші панелі (superuser / staff) =================
def staff_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *a, **k):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *a, **k)
    return wrapper


def _back(request, default):
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(nxt)
    return redirect(default)


def _score():
    return Coalesce(Sum("submissions__points", filter=Q(submissions__status="approved")), 0)


@login_required
def after_login(request):
    return redirect("panel" if request.user.is_staff else "cabinet")


@staff_required
def panel(request):
    st = dict(Submission.objects.values_list("status").annotate(n=Count("id")))
    return render(request, "panel/home.html", {
        "teachers": Teacher.objects.count(), "schools": School.objects.count(),
        "pending": st.get("pending", 0), "approved": st.get("approved", 0), "rejected": st.get("rejected", 0),
        "zavuch": Teacher.objects.filter(is_zavuch=True).count(),
        "role_pending": RoleRequest.objects.filter(status="pending").count(),
        "admins": User.objects.filter(is_staff=True).order_by("username"),
        "latest": Teacher.objects.select_related("user", "school").order_by("-user__date_joined")[:8]})


@staff_required
def panel_teachers(request):
    q, school = request.GET.get("q", "").strip(), request.GET.get("school", "")
    qs = (Teacher.objects.select_related("user", "school")
          .annotate(score=_score(), pending=Count("submissions", filter=Q(submissions__status="pending"))))
    if q:
        qs = qs.filter(Q(user__last_name__icontains=q) | Q(user__first_name__icontains=q)
                       | Q(user__username__icontains=q) | Q(subject__icontains=q))
    if school.isdigit():
        qs = qs.filter(school_id=school)
    qs = qs.order_by("-user__date_joined")
    return render(request, "panel/teachers.html", {
        "items": qs[:300], "total": qs.count(), "q": q, "school": school, "schools": School.objects.all()})


@staff_required
@require_POST
def panel_teacher_roles(request, pk):
    t = get_object_or_404(Teacher, pk=pk)
    t.is_zavuch, t.is_director = "zavuch" in request.POST, "director" in request.POST
    t.save(update_fields=["is_zavuch", "is_director"])
    messages.success(request, f"{t.short_name}: рөлдер сақталды ({t.roles_display}).")
    return _back(request, "panel_teachers")


@staff_required
def panel_submissions(request):
    status, school, q = request.GET.get("status", "pending"), request.GET.get("school", ""), request.GET.get("q", "").strip()
    qs = Submission.objects.select_related("teacher__user", "teacher__school", "criterion__category")
    if status in ("pending", "approved", "rejected"):
        qs = qs.filter(status=status)
    if school.isdigit():
        qs = qs.filter(teacher__school_id=school)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(teacher__user__last_name__icontains=q))
    return render(request, "panel/submissions.html", {
        "items": qs[:200], "total": qs.count(), "status": status, "school": school, "q": q,
        "schools": School.objects.all(), "next": request.get_full_path()})


@staff_required
@require_POST
def panel_review(request, pk, action):
    if action not in ("approve", "reject"):
        raise Http404
    s = get_object_or_404(Submission, pk=pk)
    s.review(getattr(request.user, "teacher", None), action == "approve", request.POST.get("comment", ""))
    messages.success(request, "Жазба расталды." if action == "approve" else "Жазба қабылданбады.")
    return _back(request, "panel_submissions")


def _pts(v):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= 1000 else None


@staff_required
def panel_scoring(request):
    if request.method == "POST":
        P = request.POST
        if "recalc" in P:
            n = (Submission.objects.filter(status="approved")
                 .update(points=Subquery(Criterion.objects.filter(pk=OuterRef("criterion_id")).values("points")[:1])))
            messages.success(request, f"Расталған {n} жазбаның ұпайы қазіргі ережемен қайта есептелді.")
        elif "delete" in P:
            c = get_object_or_404(Criterion, pk=P["delete"])
            try:
                c.delete()
                messages.success(request, "Критерий өшірілді.")
            except ProtectedError:
                messages.error(request, "Бұл критерий бойынша жазбалар бар, өшіруге болмайды. Оның ұпайын өзгертуге болады.")
        elif "add" in P:
            cat = get_object_or_404(Category, pk=P["add"])
            title, pts = P.get(f"nt{cat.pk}", "").strip(), _pts(P.get(f"np{cat.pk}"))
            if title and pts is not None:
                Criterion.objects.create(category=cat, title=title[:200], points=pts)
                messages.success(request, "Критерий қосылды.")
            else:
                messages.error(request, "Атауын және ұпайды (0–1000) толтырыңыз.")
        else:
            changed = 0
            for c in Criterion.objects.all():
                t, p = P.get(f"t{c.pk}", "").strip(), _pts(P.get(f"p{c.pk}"))
                if t and p is not None and (t, p) != (c.title, c.points):
                    c.title, c.points = t[:200], p
                    c.save()
                    changed += 1
            messages.success(request, f"Сақталды. Өзгерген критерий: {changed}. Жаңа ұпай тек енді расталатын жазбаларға қолданылады "
                                      "(бұрынғыларға қолдану үшін «Қайта есептеу» батырмасын басыңыз).")
        return redirect("panel_scoring")
    return render(request, "panel/scoring.html", {"cats": Category.objects.prefetch_related("criteria")})


@staff_required
def panel_schools(request):
    if request.method == "POST":
        name, district = " ".join(request.POST.get("name", "").split()), " ".join(request.POST.get("district", "").split())
        if name:
            _, new = School.objects.get_or_create(name=name[:200], district=district[:100])
            messages.success(request, "Мектеп қосылды." if new else "Мұндай мектеп бұрыннан бар.")
        else:
            messages.error(request, "Мектеп атауын жазыңыз.")
        return redirect("panel_schools")
    return render(request, "panel/schools.html", {"items": School.objects.annotate(n=Count("teacher"))})


class PwChange(SuccessMessageMixin, PasswordChangeView):
    """Кіргеннен кейін өз құпиясөзін өзгерту (мұғалім де, әкімші де)."""
    template_name = "registration/password_change_form.html"
    success_url = reverse_lazy("password_change")
    success_message = "Құпиясөз өзгертілді."

    def dispatch(self, request, *a, **k):
        request.teacher = getattr(request.user, "teacher", None) if request.user.is_authenticated else None
        return super().dispatch(request, *a, **k)

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["base_tpl"] = "panel/base.html" if self.request.user.is_staff else "cabinet/base.html"
        return ctx


@staff_required
@require_POST
def panel_user_password(request, pk):
    """Әкімші пайдаланушыға уақытша құпиясөз тағайындайды (ескі құпиясөзді көру мүмкін емес: ол хэштелген)."""
    u = get_object_or_404(User, pk=pk)
    if (u.is_staff or u.is_superuser) and not request.user.is_superuser:
        raise PermissionDenied
    pw = secrets.token_urlsafe(9)
    u.set_password(pw)
    u.save(update_fields=["password"])
    messages.success(request, f"Логин: {u.username}. Уақытша құпиясөз: {pw}. Ол тек қазір көрсетіледі, "
                              "пайдаланушы кіргеннен кейін өзгертуі керек.")
    return _back(request, "panel_teachers")


@staff_required
def panel_roles(request):
    status = request.GET.get("status", "pending")
    qs = RoleRequest.objects.select_related("teacher__user", "teacher__school")
    if status in ("pending", "approved", "rejected"):
        qs = qs.filter(status=status)
    return render(request, "panel/roles.html", {"items": qs[:200], "status": status, "next": request.get_full_path()})


@staff_required
@require_POST
def panel_role_review(request, pk, action):
    if action not in ("approve", "reject"):
        raise Http404
    r = get_object_or_404(RoleRequest, pk=pk)
    ok = action == "approve"
    r.review(request.user, ok, request.POST.get("comment", ""))
    u = r.teacher.user
    send_mail("Ustaz Portfolio: рөл сұранысы " + ("расталды" if ok else "қабылданбады"),
              f"Сәлем, {u.first_name}!\n\n«{r.wanted_display}» рөлін сұрауыңыз " + ("расталды. Кабинетте жаңа бөлімдер ашылды." if ok else "қабылданбады.")
              + (f"\nӘкімші түсініктемесі: {r.comment}" if r.comment else "") + "\n",
              None, [u.email], fail_silently=True)
    messages.success(request, "Рөл расталды." if ok else "Сұраныс қабылданбады.")
    return _back(request, "panel_roles")


# ============ Мұғалімді қосу / өшіру ============
def _delete_teacher(t):
    for s in t.submissions.all():
        s.document.delete(save=False)
    for r in t.role_requests.all():
        r.document.delete(save=False)
    t.user.delete()  # Мұғалім, жазбалар, сұраныстар каскадпен өшеді


def _added_msg(t, pw):
    return (f"Мұғалім қосылды: {t.full_name}. Логин: {t.user.username}. Құпиясөз: {pw}. "
            "Құпиясөз тек қазір көрсетіледі: мұғалімге беріңіз, ол кіргеннен кейін өзгертеді.")


@staff_required
def panel_teacher_add(request):
    form = TeacherAddForm(request.POST or None, allow_roles=True)
    if request.method == "POST" and form.is_valid():
        t, pw = form.save()
        messages.success(request, _added_msg(t, pw))
        return redirect("panel_teachers")
    return render(request, "panel/teacher_add.html", {"form": form})


@staff_required
@require_POST
def panel_teacher_delete(request, pk):
    t = get_object_or_404(Teacher.objects.select_related("user"), pk=pk)
    if t.user_id == request.user.id or t.user.is_staff:
        messages.error(request, "Әкімші тіркелгісін өшіруге болмайды.")
        return _back(request, "panel_teachers")
    name = t.full_name
    _delete_teacher(t)
    messages.success(request, f"{name} өшірілді (жазбалары мен құжаттарымен бірге).")
    return _back(request, "panel_teachers")


def _can_delete(actor, target):
    """Мектеп әкімшісі: өзін де, әкімші тіркелгісін де өшіре алмайды; директор мектеп әкімшісін өшіре алады, әкімші тек жай мұғалімді."""
    if target.pk == actor.pk or target.user.is_staff:
        return False
    if actor.is_director:
        return not target.is_director
    return not (target.is_zavuch or target.is_director)


@reviewer_required
def school_teachers(request):
    me = request.teacher
    items = list(Teacher.objects.filter(school=me.school).select_related("user")
                 .annotate(score=_score(), pending=Count("submissions", filter=Q(submissions__status="pending")))
                 .order_by("user__last_name", "user__first_name"))
    for x in items:
        x.can_delete = _can_delete(me, x)
        x.can_role = me.is_director and x.pk != me.pk and not x.user.is_staff and not x.is_director
    return render(request, "cabinet/school_teachers.html", {"items": items, "school": me.school})


@reviewer_required
def school_teacher_add(request):
    form = TeacherAddForm(request.POST or None, school=request.teacher.school)
    if request.method == "POST" and form.is_valid():
        t, pw = form.save()
        messages.success(request, _added_msg(t, pw))
        return redirect("school_teachers")
    return render(request, "cabinet/teacher_add.html", {"form": form})


@reviewer_required
@require_POST
def school_teacher_delete(request, pk):
    target = get_object_or_404(Teacher.objects.select_related("user"), pk=pk, school=request.teacher.school)
    if not _can_delete(request.teacher, target):
        raise PermissionDenied
    name = target.full_name
    _delete_teacher(target)
    messages.success(request, f"{name} өшірілді (жазбалары мен құжаттарымен бірге).")
    return redirect("school_teachers")


@reviewer_required
@require_POST
def school_teacher_admin(request, pk, action):
    """Директор өз мектебінің кез келген мұғаліміне «Әкімші» рөлін береді немесе алады."""
    me = request.teacher
    if not me.is_director or action not in ("grant", "revoke"):
        raise PermissionDenied
    target = get_object_or_404(Teacher.objects.select_related("user"), pk=pk, school=me.school)
    if target.pk == me.pk or target.user.is_staff or target.is_director:
        raise PermissionDenied
    grant = action == "grant"
    target.is_zavuch = grant
    target.save(update_fields=["is_zavuch"])
    u = target.user
    send_mail("Ustaz Portfolio: рөліңіз өзгерді",
              f"Сәлем, {u.first_name}!\n\n{me.short_name} (директор) сізге «Әкімші» рөлін " + ("берді. Кабинетте жаңа бөлімдер ашылды." if grant else "алып тастады.") + "\n",
              None, [u.email], fail_silently=True)
    messages.success(request, f"{target.short_name}: " + ("әкімші рөлі берілді." if grant else "әкімші рөлі алынды."))
    return redirect("school_teachers")


@staff_required
def panel_categories(request):
    cats = Category.objects.all()
    if request.method == "POST":
        for c in cats:
            txt = request.POST.get(f"d{c.pk}")
            if txt is not None:
                c.description = txt.strip()[:2000]
                c.save(update_fields=["description"])
        messages.success(request, "Түсініктемелер сақталды. Басты беттегі санат карточкасын басқанда көрсетіледі.")
        return redirect("panel_categories")
    return render(request, "panel/categories.html", {"cats": cats})


def category_page(request, slug):
    """Санаттың жеке беті: түсініктеме, ұпай беру тәртібі, жазба қосу батырмасы."""
    cats = list(Category.objects.prefetch_related("criteria"))
    i = next((n for n, c in enumerate(cats) if c.slug == slug), None)
    if i is None:
        raise Http404
    cat = cats[i]
    t = getattr(request.user, "teacher", None) if request.user.is_authenticated else None
    titles = {"main": "Педагог, басшы және басшының орынбасары үшін", "extra": "Педагог үшін",
              "head": "Басшы / басшының орынбасары үшін"}
    return render(request, "category.html", {
        "cat": cat, "group_title": titles.get(cat.group, ""),
        "can_add": bool(t) and (cat.group != "head" or t.can_review),
        "prev": cats[i - 1] if i > 0 else None, "next": cats[i + 1] if i + 1 < len(cats) else None})
