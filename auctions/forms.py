from django import forms
from decimal import Decimal
from django.core.validators import MinValueValidator
from .models import AuctionItem, Bid, AutoBid

class AuctionItemForm(forms.ModelForm):
    DURATION_CHOICES = [
        (1, '1 Hour'),
        (24, '1 Day'),
        (72, '3 Days'),
        (168, '1 Week'),
    ]
    duration_hours = forms.ChoiceField(choices=DURATION_CHOICES, label='Auction Duration')

    class Meta:
        model = AuctionItem
        fields = ['title', 'description', 'starting_bid', 'image', 'duration_hours']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'starting_bid': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'duration_hours': forms.Select(),
        }

    def clean_starting_bid(self):
        starting_bid = self.cleaned_data.get('starting_bid')
        if isinstance(starting_bid, Decimal):
            try:
                return Decimal(starting_bid)
            except:
                raise forms.ValidationError("Please enter a valid amount")
        return starting_bid

class BidForm(forms.ModelForm):
    class Meta:
        model = Bid
        fields = ['amount']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Enter bid amount'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.item = kwargs.pop('item', None)
        super().__init__(*args, **kwargs)
        if self.item:
            self.fields['amount'].validators.append(
                MinValueValidator(self.item.get_highest_bid() + Decimal('0.01')))
            self.fields['amount'].widget.attrs['min'] = float(self.item.get_highest_bid() + Decimal('0.01'))

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        try:
            amount = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount
            if self.item and amount <= self.item.get_highest_bid():
                raise forms.ValidationError(
                    f"Bid must be higher than ${self.item.get_highest_bid():.2f}")
            return amount
        except (TypeError, ValueError):
            raise forms.ValidationError("Please enter a valid number")
from django import forms
from .models import UserProfile

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['profile_image', 'first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'Enter first name'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Enter last name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Enter email'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and UserProfile.objects.filter(email=email).exclude(_id=self.instance._id).exists():
            raise forms.ValidationError('This email is already in use.')
        return email

    def clean_profile_image(self):
        profile_image = self.cleaned_data.get('profile_image')
        if profile_image:
            if profile_image.size > 5 * 1024 * 1024:  # 5MB limit
                raise forms.ValidationError('Image file too large (max 5MB).')
        return profile_image
class AutoBidForm(forms.ModelForm):
    class Meta:
        model = AutoBid
        fields = ['max_amount']
        widgets = {
            'max_amount': forms.NumberInput(attrs={
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Enter maximum bid amount'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.item = kwargs.pop('item', None)
        super().__init__(*args, **kwargs)
        if self.item:
            min_value = self.item.get_highest_bid() + Decimal('0.01')
            self.fields['max_amount'].validators.append(MinValueValidator(min_value))
            self.fields['max_amount'].widget.attrs['min'] = float(min_value)

    def clean_max_amount(self):
        max_amount = self.cleaned_data.get('max_amount')
        try:
            max_amount = Decimal(str(max_amount)) if not isinstance(max_amount, Decimal) else max_amount
            if self.item and max_amount <= self.item.get_highest_bid():
                raise forms.ValidationError(
                    f"Maximum bid must be higher than ${self.item.get_highest_bid():.2f}")
            return max_amount
        except (TypeError, ValueError):
            raise forms.ValidationError("Please enter a valid number")