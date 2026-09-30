from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, FloatField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, NumberRange

class LoginForm(FlaskForm):
    email = StringField('Username or Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    address = TextAreaField('Address', validators=[Length(max=200)])
    pincode = StringField('Pincode', validators=[DataRequired(), Length(min=4, max=10)])
    submit = SubmitField('Register')

class ParkingLotForm(FlaskForm):
    prime_location_name = StringField('Location Name', validators=[DataRequired()])
    price = FloatField('Price per Hour', validators=[DataRequired(), NumberRange(min=0)])
    address = TextAreaField('Address', validators=[DataRequired()])
    pin_code = StringField('Pin Code', validators=[DataRequired(), Length(min=6, max=6)])
    maximum_number_of_spots = IntegerField('Maximum Spots', validators=[DataRequired(), NumberRange(min=1, max=100)])
    submit = SubmitField('Create Parking Lot')
