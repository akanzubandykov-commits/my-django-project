import os

from django.contrib import messages
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import ai
from .lesson_models import AIUsage, Lesson
from .views import teacher_required

KINDS = [("intro", "Ұйымдастыру"), ("motivation", "Қызығушылықты ояту"), ("theory", "Теория"),
         ("practice", "Практика"), ("task", "Тапсырмалар"), ("reinforce", "Бекіту"),
         ("reflect", "Рефлексия"), ("other", "Басқа")]
KIND_LABELS = dict(KINDS)
LANG_CODES = [c for c, _ in Lesson.LANGS]
DESIGN_CODES = [c for c, _ in Lesson.DESIGNS]
MAX_STAGES = 15
MAGIC_URL = "https://magic-world-lesson-garden.lovable.app/"  # дайын сыртқы интерактивті сабақ құралы


# ---------- көмекші функциялар ----------
def _month():
    return timezone.now().strftime("%Y-%m")


def _limit():
    try:
        return int(os.environ.get("LESSON_AI_MONTHLY_LIMIT", "30"))
    except ValueError:
        return 30


def ai_left(teacher):
    if teacher.user.is_staff:
        return 999
    used = AIUsage.objects.filter(teacher=teacher, month=_month()).values_list("count", flat=True).first() or 0
    return max(0, _limit() - used)


def _spend(teacher):
    obj, _ = AIUsage.objects.get_or_create(teacher=teacher, month=_month())
    AIUsage.objects.filter(pk=obj.pk).update(count=F("count") + 1)


def _int(v, lo, hi, default):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _s(v, n):
    if isinstance(v, list):
        v = "\n".join(str(x) for x in v)
    return str(v or "").strip()[:n]


def _quiz(raw):
    out = []
    for q in (raw or [])[:15] if isinstance(raw, list) else []:
        if not isinstance(q, dict):
            continue
        opts = [_s(o, 200) for o in (q.get("options") or []) if str(o).strip()][:6]
        text = _s(q.get("q"), 300)
        if text and len(opts) >= 2:
            out.append({"q": text, "options": opts, "answer": _int(q.get("answer"), 0, len(opts) - 1, 0),
                        "explanation": _s(q.get("explanation"), 400)})
    return out


def quiz_to_text(quiz):
    blocks = []
    for q in quiz:
        lines = ["? " + q["q"]] + [("+ " if i == q["answer"] else "- ") + o for i, o in enumerate(q["options"])]
        if q["explanation"]:
            lines.append("= " + q["explanation"])
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def quiz_from_text(text):
    """«? сұрақ / - қате / + дұрыс / = түсініктеме» пішімін оқиды."""
    out, cur = [], None
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("?"):
            cur = {"q": line[1:].strip(), "options": [], "answer": 0, "explanation": ""}
            out.append(cur)
        elif cur is None:
            continue
        elif line[:2] in ("+ ", "- ") or line in ("+", "-"):
            if line[0] == "+":
                cur["answer"] = len(cur["options"])
            cur["options"].append(line[1:].strip())
        elif line.startswith("="):
            cur["explanation"] = line[1:].strip()
    return out


def normalize(c):
    """ЖИ немесе форма берген деректі қауіпсіз, біркелкі пішінге келтіреді."""
    c = c if isinstance(c, dict) else {}
    stages = []
    for s in (c.get("stages") or [])[:MAX_STAGES]:
        if not isinstance(s, dict):
            continue
        kind = s.get("kind") if s.get("kind") in KIND_LABELS else "other"
        stages.append({"name": _s(s.get("name"), 120) or "Кезең", "minutes": _int(s.get("minutes"), 0, 120, 5),
                       "kind": kind, "body": _s(s.get("body"), 6000)})
    obj = c.get("objectives") or []
    if isinstance(obj, str):
        obj = obj.splitlines()
    return {"title": _s(c.get("title"), 200), "goal": _s(c.get("goal"), 1000),
            "objectives": [_s(o, 300) for o in obj if str(o).strip()][:10], "stages": stages,
            "homework": _s(c.get("homework"), 2000), "answers": _s(c.get("answers"), 4000),
            "quiz": _quiz(c.get("quiz"))}


def _content_from_post(P):
    n = _int(P.get("n"), 0, MAX_STAGES, 0)
    stages = [{"name": P.get(f"sname{i}", ""), "minutes": P.get(f"smin{i}"), "kind": P.get(f"skind{i}"),
               "body": P.get(f"sbody{i}", "")} for i in range(n)]
    return normalize({"title": P.get("title", ""), "goal": P.get("goal", ""),
                      "objectives": P.get("objectives", "").splitlines(), "stages": stages,
                      "homework": P.get("homework", ""), "answers": P.get("answers", ""),
                      "quiz": quiz_from_text(P.get("quiz", ""))})


def _ai_gate(request, t):
    """ЖИ-ді қолдануға бола ма? Болмаса, себебін хабарлайды."""
    if not ai.available():
        messages.info(request, "ЖИ әзірге қосылмаған (кілт бапталмаған). Қолмен өңдей беріңіз.")
        return False
    if ai_left(t) <= 0:
        messages.info(request, "Осы айдағы ЖИ сұраныс шегі бітті.")
        return False
    return True


# ---------- беттер ----------
@teacher_required
def lessons(request):
    t = request.teacher
    return render(request, "cabinet/lessons.html", {"items": t.lessons.all(), "left": ai_left(t), "ai_on": ai.available(), "magic_url": MAGIC_URL})


@teacher_required
def lesson_new(request):
    t = request.teacher
    f = {"grade": "7", "language": "kk", "duration": "45", "design": "dala", "topic": "", "wishes": ""}
    ctx = {"subject": t.subject, "grades": range(1, 12), "langs": Lesson.LANGS, "designs": Lesson.DESIGNS,
           "left": ai_left(t), "ai_on": ai.available(), "f": f, "magic_url": MAGIC_URL}
    if request.method == "POST":
        P = request.POST
        grade, duration = _int(P.get("grade"), 1, 11, 7), _int(P.get("duration"), 15, 120, 45)
        lang = P.get("language") if P.get("language") in LANG_CODES else "kk"
        design = P.get("design") if P.get("design") in DESIGN_CODES else "dala"
        topic, wishes = _s(P.get("topic"), 200), _s(P.get("wishes"), 1500)
        f.update(grade=str(grade), language=lang, duration=str(duration), design=design, topic=topic, wishes=wishes)
        if not topic:
            ctx["error"] = "Тақырыпты жазыңыз."
        else:
            content = None
            if _ai_gate(request, t):
                content, err = ai.generate(t.subject, grade, lang, topic, duration, wishes)
                if content:
                    _spend(t)
                    messages.success(request, "Сабақ дайын. Қажет болса, өзгертіңіз немесе ЖИ-ге өзгеріс сұраныңыз.")
                else:
                    messages.error(request, err or "ЖИ жауап бермеді.")
            if content is None:
                content = ai.skeleton(lang, topic, duration)
                messages.info(request, "Бос қаңқа жасалды: кезеңдердің мәтінін өзіңіз толтырыңыз.")
            lesson = Lesson.objects.create(teacher=t, subject=t.subject, grade=grade, language=lang, topic=topic,
                                           duration=duration, design=design, wishes=wishes, content=normalize(content))
            return redirect("lesson_edit", lesson.pk)
    return render(request, "cabinet/lesson_new.html", ctx)


@teacher_required
def lesson_edit(request, pk):
    t = request.teacher
    lesson = get_object_or_404(Lesson, pk=pk, teacher=t)
    if request.method == "POST":
        P = request.POST
        content = _content_from_post(P)
        if P.get("design") in DESIGN_CODES:
            lesson.design = P["design"]
        st, op = content["stages"], P.get("op", "save")
        if op == "add":
            if len(st) < MAX_STAGES:
                st.append({"name": "Жаңа кезең", "minutes": 5, "kind": "other", "body": ""})
        elif op.startswith("del:"):
            i = _int(op[4:], 0, 99, -1)
            if 0 <= i < len(st):
                del st[i]
        elif op.startswith(("up:", "down:")):
            i = _int(op.split(":")[1], 0, 99, -1)
            j = i - 1 if op.startswith("up:") else i + 1
            if 0 <= i < len(st) and 0 <= j < len(st):
                st[i], st[j] = st[j], st[i]
        elif op == "ai":
            ins = _s(P.get("instruction"), 1500)
            if not ins:
                messages.error(request, "Қандай өзгеріс керек екенін жазыңыз.")
            elif _ai_gate(request, t):
                new, err = ai.revise(lesson.subject, lesson.grade, lesson.language, lesson.topic, content, ins)
                if new:
                    _spend(t)
                    content = normalize(new)
                    messages.success(request, "ЖИ өзгерісті енгізді. Қарап шығып, қажет болса түзетіңіз.")
                else:
                    messages.error(request, err or "ЖИ жауап бермеді.")
        lesson.content = normalize(content)
        lesson.save()
        if op == "save":
            messages.success(request, "Сақталды.")
        return redirect("lesson_edit", lesson.pk)
    c = normalize(lesson.content)
    return render(request, "cabinet/lesson_edit.html", {
        "lesson": lesson, "c": c, "stages": c["stages"], "obj_text": "\n".join(c["objectives"]), "kinds": KINDS, "quiz_text": quiz_to_text(c["quiz"]),
        "designs": Lesson.DESIGNS, "total": sum(s["minutes"] for s in c["stages"]),
        "left": ai_left(t), "ai_on": ai.available()})


@teacher_required
def lesson_view(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk, teacher=request.teacher)
    c = normalize(lesson.content)
    stages = [dict(s, kind_label=KIND_LABELS[s["kind"]]) for s in c["stages"]]
    return render(request, "cabinet/lesson_view.html", {
        "lesson": lesson, "c": c, "stages": stages, "total": sum(s["minutes"] for s in c["stages"])})


@teacher_required
@require_POST
def lesson_delete(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk, teacher=request.teacher)
    lesson.delete()
    messages.success(request, "Сабақ өшірілді.")
    return redirect("lessons")
