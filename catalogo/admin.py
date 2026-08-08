from django.contrib import admin

from .models import Categoria, Producto


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio', 'talla', 'color', 'stock', 'activo')
    list_filter = ('categoria', 'activo')
    search_fields = ('nombre', 'descripcion')
    list_editable = ('precio', 'stock', 'activo')
