from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'email', 'rol', 'is_staff')
    list_filter = ('rol', 'is_staff', 'is_active')

    fieldsets = UserAdmin.fieldsets + (
        ('Rol en la tienda', {'fields': ('rol',)}),
        ('Datos de entrega', {'fields': ('telefono', 'direccion')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Rol en la tienda', {'fields': ('rol',)}),
    )
