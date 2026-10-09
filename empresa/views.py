import io

import qrcode
import qrcode.image.svg
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django_otp import devices_for_user
from django_otp import login as otp_login
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from . import cargas, cuentas
from .auditoria import auditar_lectura
from .forms import CargaForm, ParametroForm, PerfilForm, PeriodoEstadoForm, UsuarioForm
from .importacion import CAMPOS_POR_TIPO, leer_dataframe, sugerir_mapeo
from .models import (
    ArchivoCargado,
    Parametro,
    PerfilImportacion,
    Periodo,
    PeriodoCerrado,
    RegistroAuditoria,
    Usuario,
)
from .permisos import requiere
from .seguridad import FormularioIngreso
from .utils import contexto_selector, periodo_desde_request


class Ingreso(LoginView):
    template_name = "empresa/ingreso.html"
    authentication_form = FormularioIngreso
    redirect_authenticated_user = True


def salud(request):
    return HttpResponse("ok")


# ---------- Doble factor ----------
def _qr_svg(url):
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode()


def configurar_2fa(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if request.user.is_verified():
        return redirect("tablero")
    if any(devices_for_user(request.user, confirmed=True)):
        return redirect("2fa_verificar")
    dispositivo = TOTPDevice.objects.filter(user=request.user, confirmed=False).first() or TOTPDevice.objects.create(
        user=request.user, name="principal", confirmed=False
    )
    if request.method == "POST":
        token = request.POST.get("token", "").replace(" ", "")
        if dispositivo.verify_token(token):
            dispositivo.confirmed = True
            dispositivo.save()
            otp_login(request, dispositivo)
            estatico = StaticDevice.objects.create(user=request.user, name="recuperacion", confirmed=True)
            codigos = []
            for _ in range(8):
                t = StaticToken.random_token()
                estatico.token_set.create(token=t)
                codigos.append(t)
            RegistroAuditoria.registrar("2fa_configurado", usuario=request.user, descripcion="Segundo factor configurado")
            return render(request, "empresa/codigos_recuperacion.html", {"codigos": codigos})
        messages.error(request, "Código incorrecto. Revisa la hora de tu celular e intenta de nuevo.")
    return render(request, "empresa/2fa_configurar.html", {"qr": _qr_svg(dispositivo.config_url), "clave": dispositivo.bin_key.hex()})


def verificar_2fa(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if request.user.is_verified():
        return redirect("tablero")
    if request.method == "POST":
        token = request.POST.get("token", "").replace(" ", "")
        for d in devices_for_user(request.user, confirmed=True):
            if d.verify_token(token):
                otp_login(request, d)
                return redirect("tablero")
        RegistroAuditoria.registrar("2fa_fallido", usuario=request.user, descripcion="Código 2FA incorrecto")
        messages.error(request, "Código incorrecto.")
    return render(request, "empresa/2fa_verificar.html")


# ---------- Cargas ----------
@requiere("cargar")
def cargas_lista(request):
    periodo = periodo_desde_request(request)
    archivos = ArchivoCargado.objects.filter(periodo=periodo).select_related("usuario", "perfil")
    ctx = {"archivos": archivos, "titulo": "Cargas", **contexto_selector(periodo)}
    return render(request, "empresa/cargas_lista.html", ctx)


@requiere("cargar")
def cargas_nueva(request):
    periodo = periodo_desde_request(request)
    form = CargaForm(request.POST or None, request.FILES or None, initial={"anio": periodo.anio, "mes": periodo.mes})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        p = Periodo.obtener(d["anio"], d["mes"])
        try:
            a = cargas.registrar_archivo(d["archivo"], d["tipo"], p, request.user, d.get("perfil"), d.get("sentido") or "")
        except cargas.ArchivoDuplicado as dup:
            messages.warning(request, "Ese archivo ya fue cargado antes (misma huella).")
            return redirect("carga_detalle", pk=dup.existente.pk)
        except PeriodoCerrado as exc:
            messages.error(request, str(exc))
        else:
            return redirect("carga_detalle", pk=a.pk)
    return render(request, "empresa/cargas_nueva.html", {"form": form, "titulo": "Nueva carga", **contexto_selector(periodo)})


@requiere("cargar")
@auditar_lectura("Previsualización de carga")
def carga_detalle(request, pk):
    a = get_object_or_404(ArchivoCargado, pk=pk)
    lectura = None
    campos = CAMPOS_POR_TIPO.get(a.tipo, [])
    if a.estado != ArchivoCargado.Estado.IMPORTADO:
        try:
            lectura = cargas.previsualizar(a)
        except Exception as exc:
            messages.error(request, f"No se pudo leer el archivo: {exc}")
    return render(request, "empresa/carga_detalle.html", {
        "a": a, "lectura": lectura, "campos": campos, "titulo": a.nombre_original,
        "vista_previa": lectura.filas[:20] if lectura else [],
    })


@requiere("cargar")
@require_POST
def carga_confirmar(request, pk):
    a = get_object_or_404(ArchivoCargado, pk=pk)
    try:
        cargas.confirmar(a, request.user, omitir_filas_con_error=bool(request.POST.get("omitir")))
    except PeriodoCerrado as exc:
        messages.error(request, str(exc))
        return redirect("carga_detalle", pk=pk)
    if a.estado == ArchivoCargado.Estado.IMPORTADO:
        from controles.tasks import ejecutar_reglas_periodo

        ejecutar_reglas_periodo.delay(a.periodo_id)
        messages.success(request, "Importación confirmada. Se están recalculando los controles del periodo.")
    else:
        messages.error(request, "La importación no se completó: revisa los errores.")
    return redirect("carga_detalle", pk=pk)


@requiere("cargar")
def carga_mapear(request, pk):
    """Crea un perfil de mapeo a partir de las columnas del archivo, desde la interfaz."""
    a = get_object_or_404(ArchivoCargado, pk=pk)
    campos = CAMPOS_POR_TIPO.get(a.tipo, [])
    with a.archivo.open("rb") as f:
        contenido = f.read()
    ref = PerfilImportacion(nombre="", tipo=a.tipo, fila_encabezado=int(request.POST.get("fila_encabezado") or 1))
    df = leer_dataframe(contenido, a.nombre_original, a.perfil or ref)
    columnas = [str(c).strip() for c in df.columns]
    if request.method == "POST":
        mapeo = {c.nombre: request.POST.get(f"campo_{c.nombre}") for c in campos if request.POST.get(f"campo_{c.nombre}")}
        nombre = request.POST.get("nombre", "").strip() or f"Perfil {a.get_tipo_display()}"
        perfil, _ = PerfilImportacion.objects.update_or_create(
            nombre=nombre, tipo=a.tipo,
            defaults=dict(mapeo=mapeo, fila_encabezado=int(request.POST.get("fila_encabezado") or 1),
                          decimal_coma=bool(request.POST.get("decimal_coma")),
                          formato_fecha=request.POST.get("formato_fecha", ""), hoja=request.POST.get("hoja", ""),
                          separador_csv=request.POST.get("separador_csv") or ","),
        )
        a.perfil = perfil
        a.save(update_fields=["perfil"])
        messages.success(request, "Perfil guardado y aplicado a esta carga.")
        return redirect("carga_detalle", pk=pk)
    sugerido = (a.perfil.mapeo if a.perfil else None) or sugerir_mapeo(a.tipo, columnas)
    return render(request, "empresa/carga_mapear.html", {
        "a": a, "campos": campos, "columnas": columnas, "sugerido": sugerido, "titulo": "Mapear columnas",
        "perfil": a.perfil,
    })


@requiere("administrar")
def perfiles_lista(request):
    form = PerfilForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Perfil creado. Asigna el mapeo desde una carga.")
        return redirect("perfiles")
    return render(request, "empresa/perfiles.html", {"perfiles": PerfilImportacion.objects.all(), "form": form, "titulo": "Perfiles de importación"})


# ---------- Configuración ----------
@requiere("administrar")
def configuracion(request):
    return render(request, "empresa/configuracion.html", {
        "parametros": Parametro.objects.all(), "titulo": "Configuración",
        "usuarios": Usuario.objects.all(), "periodos": Periodo.objects.all()[:24],
    })


@requiere("administrar")
def parametro_editar(request, pk=None):
    obj = get_object_or_404(Parametro, pk=pk) if pk else None
    form = ParametroForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Parámetro guardado.")
        return redirect("configuracion")
    return render(request, "empresa/formulario.html", {"form": form, "titulo": "Parámetro con vigencia"})


def _invitar(request, usuario):
    try:
        cuentas.enviar_invitacion(request, usuario)
    except Exception as e:  # noqa: BLE001 - se informa el motivo para que el dueño corrija el correo
        messages.error(
            request,
            f"No se pudo enviar la invitación a {usuario.email}: {type(e).__name__}. Revisa el correo (SMTP) y usa «Reenviar invitación».",
        )
        return False
    messages.success(request, f"Invitación enviada a {usuario.email}.")
    return True


@requiere("administrar")
def usuario_nuevo(request):
    form = UsuarioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        RegistroAuditoria.registrar("crear", objeto=usuario, descripcion=f"Usuario {usuario.username} creado por invitación", usuario=request.user)
        _invitar(request, usuario)
        return redirect("configuracion")
    return render(request, "empresa/formulario.html", {"form": form, "titulo": "Nuevo usuario (se invita por correo)"})


@requiere("administrar")
@require_POST
def usuario_invitar(request, pk):
    usuario = get_object_or_404(Usuario, pk=pk, is_active=True)
    if not usuario.email:
        messages.error(request, "Este usuario no tiene correo.")
    else:
        _invitar(request, usuario)
    return redirect("configuracion")


@requiere("administrar")
@require_POST
def periodo_estado(request, pk):
    p = get_object_or_404(Periodo, pk=pk)
    form = PeriodoEstadoForm(request.POST)
    if form.is_valid():
        anterior = p.estado
        p.estado = form.cleaned_data["estado"]
        p.save(update_fields=["estado"])
        RegistroAuditoria.registrar("cierre", objeto=p, descripcion=f"Periodo {p}: {anterior} → {p.estado}", usuario=request.user)
        messages.success(request, f"Periodo {p}: {p.get_estado_display()}.")
    return redirect("configuracion")


@requiere("administrar")
def auditoria(request):
    registros = RegistroAuditoria.objects.select_related("usuario")
    if request.GET.get("accion"):
        registros = registros.filter(accion=request.GET["accion"])
    if request.GET.get("usuario"):
        registros = registros.filter(usuario_texto__icontains=request.GET["usuario"])
    return render(request, "empresa/auditoria.html", {"registros": registros[:300], "titulo": "Auditoría"})
