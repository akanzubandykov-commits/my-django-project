from django.contrib import admin
from .models import Category, Criterion, RoleRequest, School, Submission, Teacher


class CriterionInline(admin.TabularInline):
    model, extra = Criterion, 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display, inlines, prepopulated_fields = ("name", "group", "order"), [CriterionInline], {"slug": ("name",)}


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display, list_filter, search_fields = ("name", "district"), ("district",), ["name", "district"]


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("full_name", "school", "is_zavuch", "is_director", "subject", "qualification", "experience")
    list_filter = ("school", "is_zavuch", "is_director")
    list_editable = ("is_zavuch", "is_director")
    search_fields = ("user__last_name", "user__username")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("title", "teacher", "criterion", "status", "points", "created_at")
    list_filter, search_fields, actions = ("status", "criterion__category"), ("title", "teacher__user__last_name"), ["approve", "reject"]

    @admin.action(description="Таңдалғандарды растау")
    def approve(self, request, qs):
        for s in qs: s.review(getattr(request.user, "teacher", None), True)

    @admin.action(description="Таңдалғандарды қабылдамау")
    def reject(self, request, qs):
        for s in qs: s.review(getattr(request.user, "teacher", None), False)


@admin.register(RoleRequest)
class RoleRequestAdmin(admin.ModelAdmin):
    list_display, list_filter = ("teacher", "want_zavuch", "want_director", "status", "created_at"), ("status",)
