from django import forms
from django.contrib.auth.forms import UserCreationForm

from .importacion import CAMPOS_POR_TIPO
from .models import ArchivoCargado, Parametro, PerfilImportacion, Periodo, Usuario


class CargaForm(forms.Form):
    tipo = forms.ChoiceField(choices=[c for c in ArchivoCargado.Tipo.choices])
    anio = forms.IntegerField(label="Año", min_value=2015, max_value=2100)
    mes = forms.IntegerField(label="Mes", min_value=1, max_value=12)
    sentido = forms.ChoiceField(
        label="Sentido (solo facturas)", required=False,
        choices=[("", "—"), ("recibida", "Recibidas (compras)"), ("emitida", "Emitidas (ventas)")],
    )
    perfil = forms.ModelChoiceField(queryset=PerfilImportacion.objects.filter(activo=True), required=False,
                                    label="Perfil de mapeo", empty_label="Detectar por nombre de columna")
    archivo = forms.FileField()

    def clean_archivo(self):
        f = self.cleaned_data["archivo"]
        if f.size > 40 * 1024 * 1024:
            raise forms.ValidationError("El archivo supera 40 MB.")
        if not f.name.lower().endswith((".xlsx", ".xlsm", ".xls", ".csv", ".txt", ".xml", ".zip", ".pdf")):
            raise forms.ValidationError("Formato no permitido.")
        return f

    def clean(self):
        d = super().clean()
        if d.get("tipo") in ("facturas_dian", "facturas_xml") and not d.get("sentido"):
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


class UsuarioForm(UserCreationForm):
    class Meta:
        model = Usuario
        fields = ["username", "first_name", "last_name", "email", "rol"]


class PeriodoEstadoForm(forms.Form):
    estado = forms.ChoiceField(choices=Periodo.Estado.choices)
