from djongo import models
from django.contrib.auth.models import User
from django.utils import timezone
import decimal 
from bson import ObjectId
from bson.decimal128 import Decimal128
from django.core.validators import MinValueValidator
from decimal import Decimal
from django import forms
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)
class UserProfile(models.Model):
    _id = models.ObjectIdField()  # MongoDB ObjectId primary key
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', to_field='id')
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)

    class Meta:
        db_table = 'user_profiles'  # Matches MongoDB collection

    def __str__(self):
        return f"{self.user.username}'s Profile"
class AuctionItem(models.Model):
    id = models.ObjectIdField(primary_key=True, default=ObjectId, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    starting_bid = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(max_length=200, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def is_auction_open(self):
        return self.end_time > timezone.now()

    def __str__(self):
        return self.title

    def get_highest_bid(self):
            highest_bid = self.bids.order_by('-amount').first()
            if highest_bid:
                amount = highest_bid.amount
                if isinstance(amount, Decimal):
                    amount = amount.to_decimal()
                elif isinstance(amount, str):
                    amount = decimal.Decimal(amount)
                return amount
            return self.starting_bid



    def is_auction_open(self):
    # Check if already marked inactive
        if not self.is_active:
            return False
    
    # Check if end time has passed
        now = timezone.now()
        if self.end_time and now >= self.end_time:
        # Close the auction
            self.is_active = False
            self.save()
        
        # Process winning bid
            highest_bid = self.bids.order_by('-amount').first()
            if highest_bid:
                try:
                    amount = Decimal(highest_bid.amount)
                    if isinstance(amount, Decimal):
                        amount = amount.to_decimal()
                    elif isinstance(amount, str):
                        amount = decimal.Decimal(amount)
                    elif not isinstance(amount, decimal.Decimal):
                        amount = decimal.Decimal(str(amount))
                
                    WinningBid.objects.update_or_create(
                        item=self,
                        defaults={'user': highest_bid.user, 'amount': amount}
                    )
                except Exception as e:
                    print(f"Error processing winning bid: {e}")
        
            return False  # Auction is closed
    
        return True  # Auction is still open

    def process_auto_bids(self):
            if not self.is_auction_open():
                return
            
            current_highest_bid = self.get_highest_bid()
            if isinstance(current_highest_bid, Decimal):
                current_highest_bid = current_highest_bid.to_decimal()
            elif isinstance(current_highest_bid, str):
                current_highest_bid = decimal.Decimal(current_highest_bid)
        
            auto_bids = self.auto_bids.exclude(user=self.created_by).filter(
                max_amount__gt=current_highest_bid
            ).order_by('-max_amount')
        
            increment = decimal.Decimal('1.00')

            for auto_bid in auto_bids:
                if auto_bid.user != self.bids.order_by('-amount').first().user:
                    max_amount = auto_bid.max_amount
                    if isinstance(max_amount, Decimal):
                        max_amount = max_amount.to_decimal()
                    elif isinstance(max_amount, str):
                        max_amount = decimal.Decimal(max_amount)
                    
                    new_bid_amount = min(current_highest_bid + increment, max_amount)
                    if new_bid_amount > current_highest_bid:
                        Bid.objects.create(
                            item=self,
                            user=auto_bid.user,
                            amount=new_bid_amount  # Already Decimal
                        )
                        current_highest_bid = new_bid_amount
                    else:
                        break

class Meta:
        app_label = 'auctions'

class Bid(models.Model):
    id = models.ObjectIdField(primary_key=True)
    item = models.ForeignKey(AuctionItem, on_delete=models.CASCADE, related_name='bids')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
    # Ensure amount is always Decimal when saved
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))
        super().save(*args, **kwargs)
    def __str__(self):
        return f"{self.user.username} bid ${self.amount} on {self.item.title}"

    class Meta:
        app_label = 'auctions'

class AutoBid(models.Model):
    id = models.ObjectIdField(primary_key=True)
    item = models.ForeignKey(AuctionItem, on_delete=models.CASCADE, related_name='auto_bids')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    max_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
    # Ensure max_amount is always Decimal
        if not isinstance(self.max_amount,Decimal):
            self.max_amount = Decimal(self.max_amount)
            print(f"Converted max_amount to Decimal: {self.max_amount}")
        super().save(*args, **kwargs)
    def __str__(self):
        return f"{self.user.username} auto-bid up to ${self.max_amount} on {self.item.title}"

    class Meta:
        app_label = 'auctions'
        unique_together = ('item', 'user')

class WinningBid(models.Model):
    item = models.OneToOneField(AuctionItem, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    # Ensure amount is always Decimal when saved
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} won {self.item.title} for ${self.amount}"

    class Meta:
        app_label = 'auctions'