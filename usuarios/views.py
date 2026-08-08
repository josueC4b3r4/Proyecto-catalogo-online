from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import PerfilForm, RegistroClienteForm


def registro(request):
    if request.user.is_authenticated:
        return redirect('inicio')

    if request.method == 'POST':
        form = RegistroClienteForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            messages.success(request, 'Tu cuenta fue creada. Bienvenido a la tienda.')
            return redirect('inicio')
    else:
        form = RegistroClienteForm()

    return render(request, 'usuarios/registro.html', {'form': form})


@login_required
def mi_perfil(request):
    if request.method == 'POST':
        form = PerfilForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tus datos fueron actualizados.')
            return redirect('mi_perfil')
    else:
        form = PerfilForm(instance=request.user)

    return render(request, 'usuarios/perfil.html', {'form': form})
