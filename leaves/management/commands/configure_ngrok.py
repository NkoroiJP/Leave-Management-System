from django.core.management.base import BaseCommand
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Configure ngrok URL for external access'

    def add_arguments(self, parser):
        parser.add_argument('ngrok_url', type=str, help='The ngrok URL (e.g., https://abc123.ngrok-free.app)')

    def handle(self, *args, **options):
        ngrok_url = options['ngrok_url']
        
        # Extract domain from URL
        if ngrok_url.startswith('https://'):
            domain = ngrok_url.replace('https://', '')
        elif ngrok_url.startswith('http://'):
            domain = ngrok_url.replace('http://', '')
        else:
            domain = ngrok_url
        
        # Remove trailing slash if present
        domain = domain.rstrip('/')
        
        # Update .env file
        env_path = os.path.join(settings.BASE_DIR, '.env')
        
        try:
            with open(env_path, 'r') as f:
                content = f.read()
            
            # Update or add the ngrok configuration
            lines = content.split('\n')
            new_lines = []
            found_host = False
            found_csrf = False
            
            for line in lines:
                if line.startswith('DJANGO_ALLOWED_HOST=') or line.startswith('# DJANGO_ALLOWED_HOST='):
                    new_lines.append(f'DJANGO_ALLOWED_HOST={domain}')
                    found_host = True
                elif line.startswith('DJANGO_CSRF_ORIGIN=') or line.startswith('# DJANGO_CSRF_ORIGIN='):
                    new_lines.append(f'DJANGO_CSRF_ORIGIN={ngrok_url}')
                    found_csrf = True
                else:
                    new_lines.append(line)
            
            # Add lines if not found
            if not found_host:
                new_lines.append(f'DJANGO_ALLOWED_HOST={domain}')
            if not found_csrf:
                new_lines.append(f'DJANGO_CSRF_ORIGIN={ngrok_url}')
            
            # Write back to file
            with open(env_path, 'w') as f:
                f.write('\n'.join(new_lines))
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully configured ngrok URL: {ngrok_url}')
            )
            self.stdout.write(
                self.style.WARNING('Please restart your Django server for changes to take effect.')
            )
            self.stdout.write(f'Domain added to ALLOWED_HOSTS: {domain}')
            self.stdout.write(f'CSRF origin configured: {ngrok_url}')
            
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR('.env file not found. Please create one first.')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error updating .env file: {e}')
            )
