import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import Http404
from .models import AuctionItem, AutoBid, Bid, WinningBid, UserProfile
from .forms import AuctionItemForm, BidForm, AutoBidForm, UserProfileForm
from django.utils import timezone
from datetime import timedelta
from bson import ObjectId
from bson.errors import InvalidId
from .forms import UserProfileForm
from .models import UserProfile
from django.core.exceptions import ObjectDoesNotExist
import logging


def is_admin(user):
    """Check if the user is an admin (staff or superuser)."""
    return user.is_authenticated and (user.is_staff or user.is_superuser)

def home(request):
    """Render the home page with a personalized greeting for authenticated users."""
    context = {}
    if request.user.is_authenticated:
        context['username'] = request.user.username
    return render(request, 'home.html', context)

def explore(request):
    try:
        items = AuctionItem.objects.all()
        for item in items:
            if item.is_active:         
                return render(request, 'explore.html', {'items': items})
    except Exception as e:
        messages.error(request, f"Error loading items: {str(e)}")
        return render(request, 'explore.html', {'items': []})

@login_required
@user_passes_test(is_admin)
def admin_panel(request):
    """Display all ongoing and past auctions for admins."""
    try:
        ongoing_auctions = AuctionItem.objects.all()
        past_auctions = AuctionItem.objects.all()
        return render(request, 'admin_panel.html', {
            'ongoing_auctions': ongoing_auctions,
            'past_auctions': past_auctions
        })
    except Exception as e:
        messages.error(request, f"Error loading admin panel: {str(e)}")
        return redirect('home')

def get_item_or_404(item_id):
    """Helper function to get item or raise 404 with proper ObjectId handling"""
    try:
        return get_object_or_404(AuctionItem, id=ObjectId(item_id))
    except (InvalidId, AuctionItem.DoesNotExist):
        raise Http404("Item not found")

from django.db import transaction
from decimal import Decimal, InvalidOperation
from bson.decimal128 import Decimal128

def item_detail(request, item_id):
    try:
        item = get_item_or_404(item_id)
        bid_form = BidForm()
        auto_bid_form = AutoBidForm()
        
        user_auto_bid = None
        if request.user.is_authenticated:
            user_auto_bid = item.auto_bids.filter(user=request.user).first()

        if not item.is_auction_open():
            return render(request, 'item_detail.html', {
                'item': item,
                'bids': item.bids.order_by('-created_at'),
                'user_auto_bid': user_auto_bid,
                'auction_closed': True
            })

        if request.method == 'POST':
            if not request.user.is_authenticated:
                messages.error(request, 'You must be logged in to place a bid.')
                return redirect('login')

            if request.user == item.created_by:
                messages.error(request, 'You cannot bid on your own item.')
                return redirect('item_detail', item_id=str(item.id))

            if 'bid_form' in request.POST:
                bid_form = BidForm(request.POST)
                if bid_form.is_valid():
                    try:
                        with transaction.atomic():
                            # Convert and validate bid amount
                            bid_amount = Decimal(bid_form.cleaned_data['amount'])
                            highest_bid = item.get_highest_bid()
                            
                            # Convert Decimal128 to Decimal if needed
                            if isinstance(highest_bid, Decimal128):
                                highest_bid = highest_bid.to_decimal()
                            
                            if bid_amount <= highest_bid:
                                messages.error(request, f'Bid must be higher than ${highest_bid}')
                                return redirect('item_detail', item_id=str(item.id))
                            
                            # Create and save the bid
                            bid = bid_form.save(commit=False)
                            bid.item = item
                            bid.user = request.user
                            
                            # Ensure amount is stored correctly
                            if isinstance(bid.amount, Decimal128):
                                bid.amount = bid.amount.to_decimal()
                            bid.amount = Decimal(bid_amount)  # or Decimal based on your model
                            bid.save()
                            
                            # Process auto bids
                            try:
                                item.process_auto_bids()
                            except Exception as e:
                                print()
                            
                            messages.success(request, 'Bid placed successfully!')
                            return redirect('item_detail', item_id=str(item.id))
                    
                    except InvalidOperation:
                        messages.error(request, 'Invalid bid amount format.')
                    except Exception as e:
                        messages.error(request, f'Error processing your bid: {str(e)}')
                        return redirect('item_detail', item_id=str(item.id))

            elif 'auto_bid_form' in request.POST:
                auto_bid_form = AutoBidForm(request.POST)
                if auto_bid_form.is_valid():
                    try:
                        with transaction.atomic():
                            max_amount = Decimal(auto_bid_form.cleaned_data['max_amount'])
                            highest_bid = item.get_highest_bid()
                            
                            if isinstance(highest_bid, Decimal128):
                                highest_bid = highest_bid.to_decimal()
                            
                            if max_amount <= highest_bid:
                                messages.error(request, f'Maximum bid must be higher than ${highest_bid}')
                                return redirect('item_detail', item_id=str(item.id))
                            
                            AutoBid.objects.update_or_create(
                                item=item,
                                user=request.user,
                                defaults={'max_amount': Decimal(max_amount)}  # or Decimal
                            )
                            messages.success(request, 'Auto-bid set successfully!')
                            return redirect('item_detail', item_id=str(item.id))
                    
                    except InvalidOperation:
                        messages.error(request, 'Invalid maximum bid format.')
                    except Exception as e:
                        messages.error(request, f'Error setting auto-bid: {str(e)}')

        # Get fresh bid list after potential updates
        bids = item.bids.order_by('-created_at')
        return render(request, 'item_detail.html', {
            'item': item,
            'bid_form': bid_form,
            'auto_bid_form': auto_bid_form,
            'bids': bids,
            'user_auto_bid': user_auto_bid,
            'auction_closed': False
        })

    except Exception as e:
        messages.error(request, f"Error loading item: {str(e)}")
        return redirect('explore')




# Set up logging
logger = logging.getLogger(__name__)

@login_required
def profile(request):
    try:
        profile = UserProfile.objects.get(user_id=request.user.id)
    except ObjectDoesNotExist:
        profile = UserProfile.objects.create(user_id=request.user.id)
        logger.info(f"Created new profile for user: {request.user.username}")
    except Exception as e:
        logger.error(f"Error fetching profile for {request.user.username}: {str(e)}")
        messages.error(request, f"Error loading profile: {str(e)}")
        return render(request, 'profile.html', {})

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            try:
                saved_profile = form.save(commit=False)
                saved_profile.user_id = request.user.id  # Ensure user_id is set
                saved_profile.save()
                logger.info(f"Saved profile for {request.user.username}: {saved_profile.__dict__}")
                messages.success(request, 'Profile updated successfully!')
                return redirect('profile')
            except Exception as e:
                logger.error(f"Error saving profile for {request.user.username}: {str(e)}")
                messages.error(request, f'Error saving profile: {str(e)}')
        else:
            logger.error(f"Form errors for {request.user.username}: {form.errors}")
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserProfileForm(instance=profile)
    auctions_won = WinningBid.objects.filter(user=request.user)
    listed_items = AuctionItem.objects.filter(created_by=request.user)
    return render(request, 'profile.html', {
        'form': form,
        'auctions_won': auctions_won,
        'listed_items': listed_items,
        'profile': profile
    })
def get_item_or_404(item_id):
    from bson import ObjectId
    from django.http import Http404
    try:
        item = AuctionItem.objects.get(id=ObjectId(item_id))
    except (AuctionItem.DoesNotExist, Exception):
        raise Http404("Item not found")
    return item
@login_required
def end_auction(request, item_id):
    #item = get_item_or_404(item_id)
    #item.is_active = False
    #item.end_time = timezone.now()  # Optional: record end time
    #item.save()

    # Show success message
    messages.success(request, "Auction ended successfully! Result will be available soon.")
    return redirect('explore')
def auction_result(request, item_id):
    try:
        item = get_item_or_404(item_id)
        if item.is_active:
            #messages.info(request, 'This auction is still active.')
            return redirect('item_detail', item_id=str(item.id))
        return render(request, 'auction_result.html', {'item': item})
    except Exception as e:
        messages.error(request, f"Error loading auction result: {str(e)}")
        return redirect('explore')

# Authentication views remain the same
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def list_item(request):
    if request.method == 'POST':
        form = AuctionItemForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                item = form.save(commit=False)
                item.created_by = request.user
                item.is_active = True
                duration_hours = int(form.cleaned_data['duration_hours'])
                item.end_time = timezone.now() + timedelta(hours=duration_hours)
                item.save()
                messages.success(request, 'Item listed successfully!')
                return redirect('explore')
            except Exception as e:
                messages.error(request, f'Error saving item: {str(e)}')
        else:
            messages.error(request, 'Error listing item. Please check the form.')
    else:
        form = AuctionItemForm()
    return render(request, 'list_item.html', {'form': form})