from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, SelectField
from wtforms.validators import DataRequired, Length, Optional

class UbicacionForm(FlaskForm):
    mueble = StringField('Mueble / Estantería', validators=[
        DataRequired(message="El campo Mueble es obligatorio."),
        Length(max=100)
    ], render_kw={"placeholder": "Ej: Mueble 1, Estantería Principal, Rack Vinilos"})

    estante = StringField('Estante / Nivel / Caja', validators=[
        DataRequired(message="El campo Estante es obligatorio."),
        Length(max=100)
    ], render_kw={"placeholder": "Ej: Estante 2, Nivel Superior, Caja 3"})

    descripcion = TextAreaField('Descripción / Notas adicionales (opcional)', validators=[
        Optional(),
        Length(max=255)
    ], render_kw={"placeholder": "Ej: Lado izquierdo, cerca de la ventana, ubicación del mueble...", "rows": 3})

    submit = SubmitField('Guardar Ubicación')


class SelloDiscograficoForm(FlaskForm):
    nombre = StringField('Nombre del Sello', validators=[
        DataRequired(message="El nombre es obligatorio."),
        Length(max=150)
    ], render_kw={"placeholder": "Ej: Nuclear Blast, Season of Mist, Osmose Productions"})

    pais_id = SelectField('País de Origen', coerce=int, validators=[])

    submit = SubmitField('Guardar Sello')


class GeneroForm(FlaskForm):
    nombre = StringField('Nombre del Género', validators=[
        DataRequired(message="El nombre es obligatorio."),
        Length(max=100)
    ], render_kw={"placeholder": "Ej: Death Metal, Thrash Metal, Black Metal"})

    descripcion = TextAreaField('Descripción / Notas (opcional)', validators=[
        Optional()
    ], render_kw={"placeholder": "Breve reseña o características del estilo...", "rows": 3})

    submit = SubmitField('Guardar Género')


class FormatoForm(FlaskForm):
    nombre = StringField('Nombre del Formato', validators=[DataRequired()])
    padre_id = SelectField('Formato Padre (Opcional)', coerce=int)
    submit = SubmitField('Guardar')