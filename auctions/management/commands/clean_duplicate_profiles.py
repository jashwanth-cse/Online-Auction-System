# auctions/management/commands/clean_duplicate_profiles.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from auctions.models import UserProfile
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Removes duplicate UserProfile instances, keeping the most recent one'

    def handle(self, *args, **kwargs):
        users = User.objects.all()
        total_duplicates = 0
        for user in users:
            profiles = UserProfile.objects.filter(user_id=user.id).order_by('-_id')
            if profiles.count() > 1:
                keep_profile = profiles.first()
                profiles.exclude(_id=keep_profile._id).delete()
                logger.info(f"Kept profile _id {keep_profile._id} for user {user.username}, deleted {profiles.count() - 1} duplicates")
                total_duplicates += profiles.count() - 1
            elif profiles.count() == 0:
                UserProfile.objects.create(user_id=user.id)
                logger.info(f"Created profile for user {user.username}")
        self.stdout.write(self.style.SUCCESS(f"Total duplicates removed: {total_duplicates}"))