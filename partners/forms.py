"""
Partners App Forms - Business Registration
"""
from django import forms
from django.contrib.auth import get_user_model
from core.models import UserRole


User = get_user_model()


class PartnerSignupForm(forms.ModelForm):
    """
    Business partner registration form.
    Creates a user with role=BUSINESS, is_business_approved=False.
    """
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mot de passe'
        }),
        min_length=8,
        label="Mot de passe"
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmer le mot de passe'
        }),
        label="Confirmation"
    )
    company_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom de votre boutique/entreprise'
        }),
        label="Nom de l'entreprise"
    )
    
    class Meta:
        model = User
        fields = ['phone_number', 'full_name', 'business_type']
        widgets = {
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+237XXXXXXXXX'
            }),
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Votre nom complet'
            }),
        }
        labels = {
            'phone_number': 'Numéro WhatsApp',
            'full_name': 'Nom complet',
        }
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if User.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError("Ce numéro est déjà enregistré.")
        return phone
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.role = UserRole.BUSINESS
        user.is_business_approved = False
        # Store company name in full_name for now
        if self.cleaned_data.get('company_name'):
            user.full_name = f"{self.cleaned_data['full_name']} - {self.cleaned_data['company_name']}"
        if commit:
            user.save()
        return user
