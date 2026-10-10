from django import forms

from .importacion import CAMPOS_POR_TIPO
from .models import ArchivoCargado, Parametro, PerfilImportacion, Periodo, Usuario
from .validacion_archivos import FORMULARIOS


class SelectPerfil(forms.Select):
    """Select de perfiles que marca cada opción con su tipo (data-tipo) para filtrarlas en pantalla."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcion = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        pk = getattr(value, "value", value)
        if pk not in ("", None):
            tipo = PerfilImportacion.objects.filter(pk=pk).values_list("tipo", flat=True).first()
            opcion["attrs"]["data-tipo"] = tipo or ""
        return opcion


class CargaForm(forms.Form):
    tipo = forms.ChoiceField(choices=[c for c in ArchivoCargado.Tipo.choices])
    anio = forms.IntegerField(label="Año", min_value=2015, max_value=2100, required=False)
    mes = forms.IntegerField(label="Mes", min_value=1, max_value=12, required=False)
    sentido = forms.ChoiceField(
        label="Sentido (solo facturas; vacío si el archivo trae la columna Emitido/Recibido)", required=False,
        choices=[("", "—"), ("recibida", "Recibidas (compras)"), ("emitida", "Emitidas (ventas)")],
    )
    perfil = forms.ModelChoiceField(queryset=PerfilImportacion.objects.filter(activo=True), required=False,
                                    label="Perfil de mapeo", empty_label="Detectar por nombre de columna",
                                    widget=SelectPerfil)
    formulario = forms.ChoiceField(
        label="Formulario (solo declaraciones)", required=False,
        choices=[("", "—")] + [(k, v[0]) for k, v in FORMULARIOS.items()],
        help_text="IVA es el formulario 300; la retención en la fuente es el 350. ICA y ReteICA son de la Secretaría de Hacienda de Bogotá.",
    )
    varios_meses = forms.BooleanField(
        label="El archivo trae varios meses: repartir por la fecha de cada registro", required=False,
        help_text="Facturas o libro auxiliar (por ejemplo, todo el año). Elige como periodo el último mes del rango.",
    )
    archivo = forms.FileField()
    subir_igual = forms.BooleanField(
        label="Subir de todas formas aunque la revisión encuentre errores", required=False,
    )

    def clean_archivo(self):
        f = self.cleaned_data["archivo"]
        if f.size > 40 * 1024 * 1024:
            raise forms.ValidationError("El archivo supera 40 MB.")
        if not f.name.lower().endswith((".xlsx", ".xlsm", ".xls", ".csv", ".txt", ".xml", ".zip", ".pdf")):
            raise forms.ValidationError("Formato no permitido.")
        return f

    def clean(self):
        d = super().clean()
        if d.get("tipo") != "terceros":
            for campo, etiqueta in (("anio", "el año"), ("mes", "el mes")):
                if not d.get(campo):
                    self.add_error(campo, f"Indica {etiqueta} del archivo.")
        if d.get("varios_meses") and d.get("tipo") not in ("facturas_dian", "facturas_xml", "auxiliar"):
            self.add_error("varios_meses", "La carga de varios meses solo aplica a facturas electrónicas y al libro auxiliar.")
        if d.get("tipo") == "declaracion" and not d.get("formulario"):
            self.add_error("formulario", "Elige qué formulario es la declaración.")
        perfil = d.get("perfil")
        if perfil and d.get("tipo") and perfil.tipo != d["tipo"]:
            self.add_error("perfil", "Ese perfil es de otro tipo de archivo. Elige uno del mismo tipo o déjalo en blanco.")
            perfil = None
        if not perfil and not d.get("sentido") and d.get("tipo") == "facturas_dian":
            # Sin sentido ni perfil: se usa el perfil DIAN (columna Grupo) si es el único de ese tipo.
            candidatos = [x for x in PerfilImportacion.objects.filter(activo=True, tipo="facturas_dian") if (x.mapeo or {}).get("sentido")]
            if len(candidatos) == 1:
                perfil = d["perfil"] = candidatos[0]
        trae_sentido = bool(perfil and (perfil.mapeo or {}).get("sentido"))  # el archivo trae la columna Emitido/Recibido
        if d.get("tipo") in ("facturas_dian", "facturas_xml") and not d.get("sentido") and not trae_sentido:
            self.add_error("sentido", "Indica si son facturas emitidas o recibidas.")
        return d


class PerfilForm(forms.ModelForm):
    class Meta:
        model = PerfilImportacion
        fields = ["nombre", "tipo", "hoja", "fila_encabezado", "separador_csv", "decimal_coma", "formato_fecha", "activo"]
        widgets = {"tipo": forms.Select(choices=[(k, k) for k in CAMPOS_POR_TIPO])}


class ParametroForm(forms.ModelForm):
    class Meta:
        model = Parametro
        fields = ["codigo", "descripcion", "tipo", "valor", "vigente_desde", "vigente_hasta", "estado", "fuente"]
        widgets = {
            "vigente_desde": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "vigente_hasta": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        help_texts = {
            "estado": "Cambiar el valor no basta: mientras siga «Por verificar» el aviso de parámetros pendientes se mantiene. "
                      "Ponlo en «Verificado» cuando el contador lo confirme, o usa el botón «Guardar y marcar como verificado».",
            "fuente": "De dónde sale o quién lo confirmó (por ejemplo: «Confirmado por la contadora, 09-oct-2026»).",
        }


class UsuarioForm(forms.ModelForm):
    """Alta de usuario por invitación: no se define contraseña; la persona la crea con el enlace que recibe por correo."""

    email = forms.EmailField(label="Correo electrónico", help_text="Aquí se envía la invitación para crear su contraseña.")

    class Meta:
        model = Usuario
        fields = ["username", "first_name", "last_name", "email", "rol"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya hay un usuario con este correo.")
        return email

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.set_unusable_password()
        if commit:
            usuario.save()
        return usuario


class PeriodoEstadoForm(forms.Form):
    estado = forms.ChoiceField(choices=Periodo.Estado.choices)
