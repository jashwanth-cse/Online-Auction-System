from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created and not UserProfile.objects.filter(user_id=instance.id).exists():
        try:
            UserProfile.objects.create(user_id=instance.id)
            logger.info(f"Created profile for user: {instance.username}")
        except Exception as e:
            logger.error(f"Error creating profile for {instance.username}: {str(e)}")

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        if not UserProfile.objects.filter(user_id=instance.id).exists():
            UserProfile.objects.create(user_id=instance.id)
            logger.info(f"Created profile for user: {instance.username}")
    except Exception as e:
        logger.error(f"Error ensuring profile for {instance.username}: {str(e)}")