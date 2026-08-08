from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    CLIENTE = 'CLIENTE'
    ADMINISTRADOR = 'ADMINISTRADOR'

    ROLES = [
        (CLIENTE, 'Cliente'),
        (ADMINISTRADOR, 'Administrador'),
    ]

    rol = models.CharField(max_length=20, choices=ROLES, default=CLIENTE)
    telefono = models.CharField(max_length=20, blank=True)
    direccion = models.TextField(blank=True)
    foto = models.ImageField(upload_to='perfiles/', blank=True, null=True)

    def __str__(self):
        return self.username
