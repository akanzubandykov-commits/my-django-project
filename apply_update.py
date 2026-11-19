"""Ustaz Portfolio: санаттарды ustaz.edu.kz сияқты 3 топқа бөлетін жаңарту (v2).

Не істейді:
  * «Сынып жетекшілік / кураторлық» санатын қосады;
  * топтар: «Педагог, басшы және басшының орынбасары үшін», «Педагог үшін»,
    «Басшы / басшының орынбасары үшін» (соңғысын тек әкімші мен директор көреді және толтырады);
  * Айыппұлдарды тексеру, Ұйымдарымен ынтымақтастық, МТБ жақсарту санаттары (15-інің түсініктемесі әзірге бос).

Қосымша (v3): әр санат батырмасы жеке бетке (/sanat/...) апарады.

Қолдану: осы файлды жоба папкасына (manage.py тұрған жерге) салып:  python apply_update.py
Содан кейін start.bat файлын екі рет басыңыз. Қайта іске қосу зиянсыз.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SEED = r'''from django.core.management.base import BaseCommand

from portfolio.models import Category, Criterion

# (тұрақты нөмір, атауы, топ, иконка): тұрақты нөмір slug-ты (c1, c2, ...) анықтайды, сондықтан бұрынғы деректер бұзылмайды.
# Тізімдегі орын = сайтта көрсетілу реті (ustaz.edu.kz сияқты).
CATS = [
    (1, "Білім сапасы", "main", "i1"), (2, "Жетістіктер", "main", "i2"), (3, "Баяндамалар", "main", "i3"),
    (4, "Басылымдар", "main", "i4"), (5, "Топтар мен жобаларға қатысу", "main", "i5"),
    (6, "Оқу-әдістемелік материалдар", "main", "i6"),
    (7, "Тәжірибе тарату", "extra", "i7"), (12, "Сынып жетекшілік / кураторлық", "extra", "i14"),
    (8, "Оқулық авторлығы, ҮОБ, педагогикалық өтіл", "extra", "i8"),
    (9, "Педагогтерді кәсіби сүйемелдеу және дамыту", "extra", "i9"), (10, "Онлайн сабақтар", "extra", "i10"),
    (11, "Психологиялық-педагогикалық қолдау және профилактикалық жұмыс", "extra", "i11"),
    # Тек мектеп әкімшісі мен директорға (ustaz.edu.kz: «Басшы / басшының орынбасары үшін»)
    (13, "Айыппұлдарды тексеру", "head", "i15"), (14, "Ұйымдарымен ынтымақтастық", "head", "i16"),
    (15, "МТБ жақсарту", "head", "i17"),
]

# Басты беттегі санат терезесінде көрсетілетін түсініктемелер (мәтіндер пайдаланушы берген құжаттан, өзгеріссіз).
# Түсініктеме бос болғанда ғана толтырылады: панельде өзгертілген мәтінді қайта жазбайды.
DESCRIPTIONS = {
    1: """Ол үш оқу жылындағы білім сапасының пайызымен (динамикада), аттестация аралық кезеңде көрсетіледі.

Дәлелдердің болуы: нәтижелерді талдау қорытындылары бар сапа мониторингі, салыстырмалы кестелер / диагностикалық құралдарға сәйкес""",
    2: """Осы критерий бойынша педагогтердің және білім алушылардың ҚР БҒМ бекіткен (№514 бұйрыққа сәйкес) немесе білім басқармалары мен бөлімдері бекіткен конкурстарға, жарыстарға, олимпиадаларға, сондай-ақ осы тізімге кірмейтін іс-шараларға қатысқаны үшін балл қосылады. Жеңіс үшін қосымша балл (+1) тек бекітілген тізімге кіретін іс-шаралар бойынша ғана беріледі.""",
    3: """Педагогтің семинарларда, конференцияларда, форумдарда, тренингтерде, біліктілікті арттыру курстарында және өзге де іс-шараларда сөз сөйлеуін растау.

Растайтын құжаттар: бұйрықтан үзінді көшірме немесе бұйрықтың көшірмесі, не бағдарлама немесе бағдарламаның көшірмесі және іс-шара материалдарына сілтеме.""",
    4: """Материал педагогтің зерттеу қызметінің нәтижесі болып табылады және Ыбырай Алтынсарин атындағы Ұлттық білім академиясы, ҚР ОМ РОӘО, Балаларды ерте дамыту институты, ҒЖБССҚК ұсынған басылымдарда жарияланған.

Дәлелдемелердің болуы: жарияланымның көшірмесі немесе басылымға сілтеме.""",
    5: """Критерий педагогтың шығармашылық (сараттаушы, жұмыс) топтарына, жобаларына немесе бәсекелік комиссияларына, жюриге қатысуын, сайысшылығын көрсетеді.

Дәлелдердің болуы: бұйрықтан үзінді (бұйрықтың көшірмесі), хат (хаттың көшірмесі).""",
    6: """Материалды педагог дайындаған және тиісті деңгейдегі оқу-әдістемелік кеңес ұсынған (мысалы, білім беру ұйымының әдістемелік кеңесі, аудандық немесе қалалық білім бөлімінің кеңесі және т.б.).

Дәлелдемелердің болуы: оқу-әдістемелік кеңес хаттамасынан үзінді, материалдарға сілтеме.""",
    7: """Практиканы тарату оқу-әдістемелік материалдар немесе бағдарламалар негізінде жүргізіледі. Педагог өз тәжірибесін әртүрлі нысандар арқылы таратады, оның ішінде шеберлік сыныптарын өткізу, сондай-ақ материалдарды цифрлық платформаларда орналастыру, мысалы, бейнехостингтерде жариялау кіреді.

Дәлелдемелердің болуы: бұйрықтан үзінді көшірме немесе бұйрықтың көшірмесі, анықтамалар, бағдарлама немесе бағдарламаның көшірмесі.""",
    8: """Үлгілік оқу бағдарламасын (ҮОБ) әзірлеу, білім беру саласындағы уәкілетті орган бекіткен басылып шыққан оқулықтың авторлығы (тең авторлығы) немесе үздіксіз педагогикалық өтіл туралы деректер енгізіледі. Бағыттардың кем дегенде біреуі толтырылса, критерий бойынша балл есептеледі.

Дәлелдемелердің болуы: ҮОБ/оқулықтың көшірмесі, жарияланымға сілтеме, жұмыс тобына (авторлық ұжымға) енгізу туралы бұйрықтың көшірмесі, еңбек қызметін растайтын құжаттардың көшірмесі.""",
    9: """Білім беру ұйымы деңгейінде кәсіби қызметке алғаш кіріскен педагогті және (немесе) біліктілік санаты төмен педагогті кәсіби сүйемелдеу және дамыту көрсетіледі.

Дәлелдемелердің болуы: білім беру ұйымының басшысы бекіткен сүйемелдеу жұмысының жоспары және сүйемелдеу нәтижелілігінің растамасы.""",
    10: """Видеоконференция байланысы арқылы онлайн форматында ашық сабақтарды (сыныптай сабақтар, іс-шаралар) өткізу. Сабақ жазбасының сілтемесі бақылаушылар бақылау парағын толтырғанда пайдаланылады.""",
    11: """Балл-балға қасуды, өзөндік бұзғыншы мінез-құлықты және құқық бұзуларын азайту жұмысының нәтижелігі, сондай-ақ ата-аналарды психолого-педагогикалық қолдаумен қамту жүргіленеді.

Дәлелдеу құжаттарының болуы: білім беру ұйымының басшысының анықтамасы.""",
    12: """Критерий бағаланады, бірақ барлығына міндетті емес.

Дәлелдердің болуы: бұйрықтан үзінді (бұйрықтың көшірмесі), тәрбие жұмысының талдамасы – болған кезде.""",
    13: """Бұл ішкі істер органдары тарапынан (тиісті мемлекеттік органнан құжат ұсыну). Критерий басшының портфолиосына қатысты. Білім беру ұйымдарында айыппұл санкцияларының жоқтығын растайтын құжат дәлел болып табылады. Ұпайлар айыппұлдың жоқтығы үшін беріледі""",
    14: """Білім беру ұйымы басқа ұйымдармен ынтымақтаса алады. Мұндай ынтымақтастық Шартпен бекітіледі. Мысалы, мектеп ғылыми-әдістемелік қолдау көрсету тұрғысынан университетпен келісім-шарт жасай алады""",
}

# ЖОБА ҮЛГІСІ: ұпайларды /admin/ арқылы өз ережеңізге сай өзгертіңіз
LEVELS = [("Мектеп деңгейі", 1), ("Аудан / қала деңгейі", 2), ("Облыс деңгейі", 3),
          ("Республика деңгейі", 5), ("Халықаралық деңгей", 8)]


class Command(BaseCommand):
    help = "Санаттар мен үлгі критерийлерді жүктейді"

    def handle(self, *a, **k):
        for pos, (key, name, grp, icon) in enumerate(CATS, 1):
            c, created = Category.objects.get_or_create(slug=f"c{key}", defaults=dict(
                name=name, icon=icon, group=grp, order=pos, description=DESCRIPTIONS.get(key, "")))
            changed = []
            if not created and (c.order, c.group, c.icon) != (pos, grp, icon):
                c.order, c.group, c.icon = pos, grp, icon
                changed += ["order", "group", "icon"]
            if not c.description and DESCRIPTIONS.get(key):
                c.description = DESCRIPTIONS[key]
                changed.append("description")
            if changed:
                c.save(update_fields=changed)
            for t, pts in LEVELS:
                Criterion.objects.get_or_create(category=c, title=t, defaults=dict(points=pts))
        self.stdout.write(self.style.SUCCESS("Дайын"))
'''
ICONS = {
    "i14": '<symbol id="i14" viewBox="0 0 24 24"><rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4h6v3H9zM8.5 13l2.5 2.5 4.5-5"/></symbol>',
    "i15": '<symbol id="i15" viewBox="0 0 24 24"><path d="M6 3h8l4 4v4M6 3v18h6"/><circle cx="16" cy="16" r="3.5"/><path d="M18.6 18.6L21 21"/></symbol>',
    "i16": '<symbol id="i16" viewBox="0 0 24 24"><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M8.2 11l7.6-4M8.2 13l7.6 4"/></symbol>',
    "i17": '<symbol id="i17" viewBox="0 0 24 24"><path d="M3 21h18M5 21V10l7-5 7 5v11M9 21v-6h6v6M12 5V2"/></symbol>',
}
RENAME = [
    ('("Негізгі бағыттар", cats.filter(group="main")),', '("Педагог, басшы және басшының орынбасары үшін", cats.filter(group="main")),'),
    ('("Қосымша бағыттар", cats.filter(group="extra"))]}', '("Педагог үшін", cats.filter(group="extra"))]}'),
    ('("Негізгі бағыттар", Category.objects.filter(group="main")),', '("Педагог, басшы және басшының орынбасары үшін", Category.objects.filter(group="main")),'),
    ('("Қосымша бағыттар", Category.objects.filter(group="extra"))]})', '("Педагог үшін", Category.objects.filter(group="extra"))]})'),
]
HEAD = "Басшы / басшының орынбасары үшін"
EDITS = [  # (шарт: бұл жол болмаса ғана қолданылады, іздеу, ауыстыру)
    ('cats.filter(group="head")', 'cats.filter(group="extra"))]}',
     'cats.filter(group="extra")),\n                                      ("' + HEAD + '", cats.filter(group="head"))]}'),
    ('Category.objects.filter(group="head")', 'Category.objects.filter(group="extra"))]})',
     'Category.objects.filter(group="extra"))]\n        + ([("' + HEAD + '", Category.objects.filter(group="head"))] if request.teacher.can_review else [])})'),
    ('cat.group == "head"', '    cat = get_object_or_404(Category, slug=slug)\n',
     '    cat = get_object_or_404(Category, slug=slug)\n    if cat.group == "head" and not request.teacher.can_review:\n        raise PermissionDenied\n'),
    ('"group__in"', 'cats = list(Category.objects.annotate(pts=Coalesce(Sum(',
     'cats = list(Category.objects.filter(**({} if t.can_review else {"group__in": ["main", "extra"]})).annotate(pts=Coalesce(Sum('),
]
CTA_OLD = "{% if user.is_authenticated and user.teacher %}<a class=\"btn btn-gold\" href=\"{% url 'enter_form'"
CTA_NEW = "{% if user.is_authenticated and user.teacher and c.group != 'head' or user.is_authenticated and user.teacher.can_review %}<a class=\"btn btn-gold\" href=\"{% url 'enter_form'"


# ---- 3-нұсқа: әр санаттың жеке беті /sanat/<slug>/ (батырма басқанда түсініктеме БЕТІ ашылады)
CARD_OLD = '<button type="button" class="icard" data-open="cat{{ c.pk }}"><svg class="ic" aria-hidden="true"><use href="#{{ c.icon }}"/></svg><b>{{ c.name }}</b></button>'
CARD_NEW = '<a class="icard" href="{% url \'category\' c.slug %}"><svg class="ic" aria-hidden="true"><use href="#{{ c.icon }}"/></svg><b>{{ c.name }}</b></a>'
URL_ANCHOR = '    path("after-login/", views.after_login, name="after_login"),\n'
URL_LINE = '    path("sanat/<slug:slug>/", views.category_page, name="category"),\n'
CATEGORY_VIEW = '''

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
'''
CATEGORY_TEMPLATE = '''{% extends "base.html" %}
{% block title %}{{ cat.name }}: Ustaz Portfolio{% endblock %}
{% block content %}
<main class="wrap authbox" style="max-width:820px">
  <p class="crumb"><a href="{% url 'home' %}#sanattar">Басты бет</a> &rsaquo; {{ group_title }}</p>
  <div class="cmain">
    <div class="cathead"><svg class="ic" style="width:44px;height:44px" aria-hidden="true"><use href="#{{ cat.icon }}"/></svg><h1 class="ph" style="margin:0;font-size:26px">{{ cat.name }}</h1></div>
    <div class="catdesc">{% if cat.description %}{{ cat.description|linebreaks }}{% else %}<p class="sub" style="margin:0">Бұл бағыт бойынша түсініктеме жақында қосылады.</p>{% endif %}</div>
    {% if cat.criteria.all %}<p class="fs" style="margin-top:20px">Ұпай беру тәртібі</p>
    <table class="tbl"><tbody>{% for k in cat.criteria.all %}<tr><td>{{ k.title }}</td><td class="num"><b>{{ k.points }}</b> ұпай</td></tr>{% endfor %}</tbody></table>{% endif %}
    <p style="margin:22px 0 0">{% if can_add %}<a class="btn btn-gold" href="{% url 'enter_form' cat.slug %}">Осы бағыт бойынша жазба қосу</a>{% elif user.is_authenticated %}<small style="color:var(--muted)">Бұл бағытты тек мектеп әкімшісі мен директор толтырады.</small>{% else %}<a class="btn btn-gold" href="{% url 'register' %}">Тіркеліп бастау</a> <a class="btn btn-line" href="{% url 'login' %}">Кіру</a>{% endif %}</p>
  </div>
  <div class="catnav">
    {% if prev %}<a class="btn btn-line btn-sm" href="{% url 'category' prev.slug %}">&lsaquo; {{ prev.name|truncatechars:34 }}</a>{% else %}<span></span>{% endif %}
    {% if next %}<a class="btn btn-line btn-sm" href="{% url 'category' next.slug %}">{{ next.name|truncatechars:34 }} &rsaquo;</a>{% endif %}
  </div>
</main>
{% endblock %}
'''
CATEGORY_CSS = """
.crumb{color:var(--muted);font-size:14px;margin:0 0 12px}.crumb a{color:var(--link)}
.cathead{display:flex;align-items:center;gap:14px;margin-bottom:16px}
.catnav{display:flex;justify-content:space-between;gap:12px;margin-top:20px;flex-wrap:wrap}
"""


def p(*parts):
    return os.path.join(ROOT, *parts)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def main():
    if not os.path.exists(p("manage.py")):
        sys.exit("Қате: бұл файлды manage.py тұрған жоба папкасына салыңыз.")
    done, warn = [], []

    seed_path = p("portfolio", "management", "commands", "seed.py")
    if not os.path.exists(seed_path):
        sys.exit("Қате: portfolio/management/commands/seed.py табылмады.")
    old = read(seed_path)
    if 'Бұл ішкі істер органдары' not in old:
        write(seed_path + ".bak", old)
        write(seed_path, SEED)
        done.append("seed.py жаңартылды (көшірмесі seed.py.bak)")

    icons_path = p("templates", "_icons.html")
    icons = read(icons_path)
    added = [k for k, v in ICONS.items() if 'id="%s"' % k not in icons]
    if added and "</defs>" in icons:
        write(icons_path, icons.replace("</defs>", "".join(ICONS[k] for k in added) + "</defs>", 1))
        done.append("иконкалар қосылды: " + ", ".join(added))

    views_path = p("portfolio", "views.py")
    views, changed = read(views_path), 0
    for a, b in RENAME:
        if a in views:
            views, changed = views.replace(a, b, 1), changed + 1
    for marker, find, repl in EDITS:
        if marker in views:
            continue
        if find in views:
            views, changed = views.replace(find, repl, 1), changed + 1
        else:
            warn.append("views.py: орын табылмады (" + marker + ")")
    if changed:
        write(views_path, views)
        done.append("views.py жаңартылды (%d өзгеріс)" % changed)

    home_path = p("templates", "home.html")
    home = read(home_path)
    if CTA_OLD in home:
        write(home_path, home.replace(CTA_OLD, CTA_NEW, 1))
        done.append("home.html: батырма шарты жаңартылды")

    # ---- әр санаттың жеке беті
    tpl_path = p("templates", "category.html")
    if not os.path.exists(tpl_path):
        write(tpl_path, CATEGORY_TEMPLATE)
        done.append("category.html (санат беті) жасалды")
    urls_path = p("portfolio", "urls.py")
    urls = read(urls_path)
    if 'name="category"' not in urls:
        if URL_ANCHOR in urls:
            write(urls_path, urls.replace(URL_ANCHOR, URL_ANCHOR + URL_LINE, 1))
            done.append("urls.py: /sanat/<slug>/ жолы қосылды")
        else:
            warn.append("urls.py: after_login жолы табылмады")
    views = read(views_path)
    if "def category_page" not in views:
        write(views_path, views.rstrip("\n") + "\n" + CATEGORY_VIEW)
        done.append("views.py: category_page қосылды")
    home = read(home_path)
    if CARD_OLD in home:
        write(home_path, home.replace(CARD_OLD, CARD_NEW))
        done.append("home.html: санат батырмалары беттерге сілтеме болды")
    css_path = p("static", "css", "site.css")
    if os.path.exists(css_path):
        css = read(css_path)
        if ".catnav" not in css:
            write(css_path, css + CATEGORY_CSS)
            done.append("site.css: стильдер қосылды")


    print("\n".join(done) if done else "Өзгеріс қажет емес: жаңарту бұрын қолданылған.")
    for w in warn:
        print("ЕСКЕРТУ:", w)
    print("Енді start.bat файлын екі рет басыңыз.")


if __name__ == "__main__":
    main()
