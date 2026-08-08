from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy

from catalogo import views as catalogo_views
from usuarios import views as usuarios_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', catalogo_views.inicio, name='inicio'),
    path('catalogo/', include('catalogo.urls')),
    path('carrito/', include('carrito.urls')),
    path('pedidos/', include('pedidos.urls')),
    path('registro/', usuarios_views.registro, name='registro'),
    path('perfil/', usuarios_views.mi_perfil, name='mi_perfil'),
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='usuarios/login.html',
            redirect_authenticated_user=True,
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path(
        'recuperar/',
        auth_views.PasswordResetView.as_view(
            template_name='usuarios/recuperar.html',
            email_template_name='usuarios/recuperar_correo.txt',
            subject_template_name='usuarios/recuperar_asunto.txt',
            success_url=reverse_lazy('password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'recuperar/enviado/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='usuarios/recuperar_enviado.html',
        ),
        name='password_reset_done',
    ),
    path(
        'recuperar/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='usuarios/recuperar_confirmar.html',
            success_url=reverse_lazy('password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'recuperar/listo/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='usuarios/recuperar_listo.html',
        ),
        name='password_reset_complete',
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
